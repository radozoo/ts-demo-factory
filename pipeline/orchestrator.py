"""
Pipeline orchestrator — runs all steps in order, threading GUIDs between steps.

Usage:
    # Dynamic (LLM schema):
    from pipeline.orchestrator import run_pipeline
    run_pipeline("Škoda Auto", table_defs=[...], joins=[...])

    # Retail fallback (hardcoded schema):
    run_pipeline("Demo Corp")
"""
from __future__ import annotations

from dataclasses import replace as dc_replace

from config.settings import Settings
from ts_client.auth import ThoughtSpotAuth
from ts_client.tml_api import TMLClient
from schema.retail.tables import ALL_TABLES, TableDef
from schema.retail.data_gen import generate_rows
from snowflake_client.loader import create_table, bulk_insert
from tml_builder.table_builder import build_table_tml
from tml_builder.model_builder import build_model_tml
from tml_builder.liveboard_builder import build_liveboard_tml


# ── Helpers for dynamic schema ────────────────────────────────────────────────

def _display_name(col_name: str) -> str:
    return col_name.replace("_", " ").title()


def _find_fact_name(table_defs: list[TableDef], joins: list[dict]) -> str:
    if joins:
        return joins[0]["fact"]
    for td in table_defs:
        if "FACT" in td.name.upper():
            return td.name
    return table_defs[0].name


def _build_model_columns(table_defs: list[TableDef]) -> list[dict]:
    """Convert TableDef list → model column specs with deduplicated display names."""
    cols: list[dict] = []
    seen: dict[str, int] = {}
    for tdef in table_defs:
        for col in tdef.columns:
            base = _display_name(col.name)
            if base in seen:
                seen[base] += 1
                name = f"{base} ({seen[base]})"
            else:
                seen[base] = 1
                name = base
            n = col.name.upper()
            if col.column_type == "MEASURE":
                agg = "AVERAGE" if any(
                    x in n for x in ("DISCOUNT", "RATE", "RATIO", "PCT", "PERCENT", "MARGIN")
                ) else "SUM"
            else:
                agg = None
            cols.append({
                "name": name,
                "column_id": f"{tdef.name}::{col.name}",
                "column_type": col.column_type,
                "aggregation": agg,
            })
    return cols


def _build_charts(
    table_defs: list[TableDef],
    joins: list[dict],
    model_cols: list[dict],
    fact_name: str,
) -> list[dict]:
    """Build chart specs for the liveboard — one chart per join (dim table)."""
    tdef_map = {td.name: td for td in table_defs}
    fact_tdef = tdef_map.get(fact_name)
    if not fact_tdef:
        return []

    fact_col_ids = {f"{fact_name}::{c.name}" for c in fact_tdef.columns}
    fact_measures = [
        mc for mc in model_cols
        if mc["column_id"] in fact_col_ids and mc["column_type"] == "MEASURE"
    ]
    if not fact_measures:
        return []

    pm = fact_measures[0]  # primary measure
    if pm["aggregation"] == "AVERAGE":
        search_prefix = "average "
        measure_resolved = f"Average {pm['name']}"
    else:
        search_prefix = ""
        measure_resolved = f"Total {pm['name']}"

    chart_types = ["BAR", "COLUMN", "PIE", "BAR", "COLUMN"]
    charts: list[dict] = []

    for i, join in enumerate(joins):
        dim_tdef = tdef_map.get(join["dim"])
        if not dim_tdef:
            continue

        # First non-PK VARCHAR ATTRIBUTE, or any non-PK ATTRIBUTE as fallback
        attr_col = next(
            (c for c in dim_tdef.columns
             if not c.is_pk and c.column_type == "ATTRIBUTE" and c.ts_data_type == "VARCHAR"),
            next(
                (c for c in dim_tdef.columns if not c.is_pk and c.column_type == "ATTRIBUTE"),
                None,
            ),
        )
        if not attr_col:
            continue

        attr_col_id = f"{join['dim']}::{attr_col.name}"
        attr_mc = next((mc for mc in model_cols if mc["column_id"] == attr_col_id), None)
        if not attr_mc:
            continue

        attr_name = attr_mc["name"]
        charts.append({
            "title": f"{pm['name']} by {attr_name}",
            "search_query": f"{search_prefix}[{pm['name']}] [{attr_name}]",
            "attr_resolved": attr_name,
            "measure_resolved": measure_resolved,
            "chart_type": chart_types[i % len(chart_types)],
        })

    return charts


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    customer_name: str,
    industry: str = "retail",
    focus: str = "",
    row_count: int = 10_000,
    table_defs: list[TableDef] | None = None,
    joins: list[dict] | None = None,
    skip_snowflake: bool = False,
    charts: list[dict] | None = None,
    years: int = 2,
    patterns: list[str] | None = None,
) -> dict:
    """
    Full pipeline:
      A. Create Snowflake tables + load dummy data
      B. Import Table TMLs → get table GUIDs
      C. Import Model TML → get model GUID
      D. Import Liveboard TML → get liveboard GUID

    If table_defs + joins provided → dynamic LLM-driven schema.
    Otherwise → retail fallback (hardcoded schema).
    """
    settings = Settings.from_env()
    auth = ThoughtSpotAuth(settings)
    client = TMLClient(settings, auth)

    safe_name = customer_name.replace(" ", "_").upper()
    dynamic = table_defs is not None and joins is not None

    if dynamic:
        # Prefix all table names with customer name to avoid clashes across demos
        prefix = safe_name + "_"
        name_map = {td.name: prefix + td.name for td in table_defs}
        active_tables = [dc_replace(td, name=prefix + td.name) for td in table_defs]
        joins = [
            {**j, "fact": name_map[j["fact"]], "dim": name_map[j["dim"]]}
            for j in joins
        ]
    else:
        active_tables = ALL_TABLES

    # ── Step A: Snowflake ──────────────────────────────────────────
    if skip_snowflake:
        print("[Pipeline] Skipping Snowflake (--skip-snowflake flag set)")
    else:
        print(f"[Pipeline] Loading {row_count} rows into Snowflake for each table…")
        for tdef in active_tables:
            create_table(settings, tdef, drop_if_exists=True)
            rows = generate_rows(tdef, row_count, years=years, patterns=patterns)
            bulk_insert(settings, tdef, rows)
            print(f"  ✓ {tdef.name} ({len(rows)} rows)")

    # ── Step B: Import Tables ──────────────────────────────────────
    print("[Pipeline] Importing Table TMLs…")
    table_guids: dict[str, str] = {}
    for tdef in active_tables:
        tml = build_table_tml(
            tdef, settings.ts_connection_name, settings.sf_database, settings.sf_schema
        )
        results = client.import_tml([tml], policy="PARTIAL", create_new=True)
        guid = results[0].get("response", {}).get("header", {}).get("id_guid")
        if guid is None:
            status_code = results[0].get("response", {}).get("status", {}).get("status_code", "?")
            error_msg = results[0].get("response", {}).get("status", {}).get("error_message", "")
            print(f"  ✗ {tdef.name} → None (status={status_code}) {error_msg[:120]}")
        else:
            print(f"  ✓ {tdef.name} → {guid}")
        table_guids[tdef.name] = guid

    failed_tables = [name for name, guid in table_guids.items() if guid is None]
    if failed_tables:
        raise RuntimeError(
            f"[Pipeline] Table import failed — no GUID for: {failed_tables}. "
            "Aborting before model import to avoid broken TML with fqn: None."
        )

    # ── Step C: Cleanup + Import Model ────────────────────────────
    model_name = f"{safe_name}_Analytics"
    lb_name = f"{safe_name}_Dashboard"
    print("[Pipeline] Cleaning up existing TS objects…")
    client.delete_by_name([lb_name], "LIVEBOARD")
    client.delete_by_name([model_name], "LOGICAL_TABLE")
    print("  ✓ Cleanup done")

    print("[Pipeline] Importing Model TML…")
    if dynamic:
        fact_name = _find_fact_name(active_tables, joins)
        model_cols = _build_model_columns(active_tables)
        model_tml = build_model_tml(
            "dynamic/model.tml.j2",
            {
                "model_name": model_name,
                "table_guids": table_guids,
                "fact_name": fact_name,
                "joins": joins,
                "model_columns": model_cols,
            },
        )
    else:
        model_tml = build_model_tml(
            "retail/model.tml.j2",
            {"model_name": model_name, "table_guids": table_guids},
        )
    model_results = client.import_tml([model_tml], policy="PARTIAL", create_new=True)
    model_guid = model_results[0].get("response", {}).get("header", {}).get("id_guid")
    if model_guid is None:
        status_code = model_results[0].get("response", {}).get("status", {}).get("status_code", "?")
        error_msg = model_results[0].get("response", {}).get("status", {}).get("error_message", "")
        raise RuntimeError(
            f"[Pipeline] Model import failed (status={status_code}): {error_msg[:300]}\n"
            "Aborting before liveboard import."
        )
    print(f"  ✓ Model → {model_guid}")

    # ── Step D: Import Liveboard ───────────────────────────────────
    print("[Pipeline] Importing Liveboard TML…")
    if dynamic:
        # Validate AI charts have required keys; fall back to auto-generated if not
        KPI_REQUIRED = {"title", "search_query", "measure_resolved", "chart_type"}
        CHART_REQUIRED = {"title", "search_query", "attr_resolved", "measure_resolved", "chart_type"}
        if charts:
            valid = all(
                KPI_REQUIRED.issubset(c.keys()) if c.get("chart_type") == "KPI"
                else CHART_REQUIRED.issubset(c.keys())
                for c in charts
            )
            if not valid:
                print("  ⚠ AI charts missing required keys — falling back to auto-generated charts")
                charts = None
        if not charts:
            charts = _build_charts(active_tables, joins, model_cols, fact_name)
        lb_tml = build_liveboard_tml(
            "dynamic/liveboard.tml.j2",
            {
                "liveboard_name": lb_name,
                "model_name": model_name,
                "model_guid": model_guid,
                "charts": charts,
            },
        )
    else:
        lb_tml = build_liveboard_tml(
            "retail/liveboard.tml.j2",
            {"liveboard_name": lb_name, "model_name": model_name, "model_guid": model_guid},
        )
    lb_results = client.import_tml([lb_tml], policy="PARTIAL", create_new=True)
    lb_guid = lb_results[0].get("response", {}).get("header", {}).get("id_guid")
    if lb_guid is None:
        status_code = lb_results[0].get("response", {}).get("status", {}).get("status_code", "?")
        error_msg = lb_results[0].get("response", {}).get("status", {}).get("error_message", "")
        print(f"  ✗ Liveboard import failed (status={status_code}): {error_msg[:300]}")
    else:
        print(f"  ✓ Liveboard → {lb_guid}")

    return {
        "table_guids": table_guids,
        "model_guid": model_guid,
        "liveboard_guid": lb_guid,
    }
