"""
Pipeline orchestrator — runs all steps in order, threading GUIDs between steps.

Usage (Phase 2+):
    from pipeline.orchestrator import run_pipeline
    run_pipeline(customer_name="Acme Corp", industry="retail", focus="EMEA")
"""
from __future__ import annotations

from config.settings import Settings
from ts_client.auth import ThoughtSpotAuth
from ts_client.tml_api import TMLClient
from schema.retail.tables import ALL_TABLES
from schema.retail.data_gen import generate_rows
from snowflake_client.loader import create_table, bulk_insert
from tml_builder.table_builder import build_table_tml
from tml_builder.worksheet_builder import build_worksheet_tml
from tml_builder.liveboard_builder import build_liveboard_tml


def run_pipeline(
    customer_name: str,
    industry: str = "retail",
    focus: str = "",
    row_count: int = 10_000,
) -> dict:
    """
    Full pipeline:
      1. Create Snowflake tables + load dummy data
      2. Import Table TMLs → get table GUIDs
      3. Import Worksheet TML → get worksheet GUID
      4. Import Liveboard TML → get liveboard GUID

    Returns dict with all GUIDs.
    """
    settings = Settings.from_env()
    auth = ThoughtSpotAuth(settings)
    client = TMLClient(settings, auth)

    safe_name = customer_name.replace(" ", "_").upper()

    # ── Step A: Snowflake ──────────────────────────────────────────
    print(f"[Pipeline] Loading {row_count} rows into Snowflake for each table…")
    for table_def in ALL_TABLES:
        create_table(settings, table_def, drop_if_exists=True)
        rows = generate_rows(table_def, row_count)
        bulk_insert(settings, table_def, rows)
        print(f"  ✓ {table_def.name} ({len(rows)} rows)")

    # ── Step B: Import Tables ──────────────────────────────────────
    print("[Pipeline] Importing Table TMLs…")
    table_guids: dict[str, str] = {}
    for table_def in ALL_TABLES:
        tml = build_table_tml(table_def, settings.ts_connection_name)
        results = client.import_tml([tml], policy="PARTIAL", create_new=True)
        guid = results[0].get("response", {}).get("header", {}).get("id_guid")
        table_guids[table_def.name] = guid
        print(f"  ✓ {table_def.name} → {guid}")

    # ── Step C: Import Worksheet ───────────────────────────────────
    print("[Pipeline] Importing Worksheet TML…")
    ws_name = f"{safe_name}_Retail_Analytics"
    ws_tml = build_worksheet_tml(
        "retail/worksheet.tml.j2",
        {"worksheet_name": ws_name, "table_guids": table_guids},
    )
    ws_results = client.import_tml([ws_tml], policy="PARTIAL", create_new=True)
    ws_guid = ws_results[0].get("response", {}).get("header", {}).get("id_guid")
    print(f"  ✓ Worksheet → {ws_guid}")

    # ── Step D: Import Liveboard ───────────────────────────────────
    print("[Pipeline] Importing Liveboard TML…")
    lb_name = f"{safe_name}_Retail_Dashboard"
    lb_tml = build_liveboard_tml(
        "retail/liveboard.tml.j2",
        {"liveboard_name": lb_name, "worksheet_name": ws_name, "worksheet_guid": ws_guid},
    )
    lb_results = client.import_tml([lb_tml], policy="PARTIAL", create_new=True)
    lb_guid = lb_results[0].get("response", {}).get("header", {}).get("id_guid")
    print(f"  ✓ Liveboard → {lb_guid}")

    return {
        "table_guids": table_guids,
        "worksheet_guid": ws_guid,
        "liveboard_guid": lb_guid,
    }
