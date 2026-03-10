"""
Re-run only the ThoughtSpot part of the pipeline using existing Snowflake tables.

Reads schema_cache.json, rebuilds table_defs/joins, then imports Tables → Model → Liveboard.
Snowflake is skipped entirely.

Usage:
    python -m scripts.rerun_ts_only
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from pipeline.orchestrator import run_pipeline
from scripts.schema_to_pipeline import json_to_table_defs, json_to_joins, align_fk_ranges

CACHE = Path(__file__).parent.parent / "schema_cache.json"


def main() -> None:
    if not CACHE.exists():
        print(f"[ERROR] {CACHE} not found. Run a full pipeline first.")
        raise SystemExit(1)

    data = json.loads(CACHE.read_text())
    schema = data["schema"]
    config = data.get("config", {})

    table_defs = json_to_table_defs(schema)
    joins = json_to_joins(schema)
    align_fk_ranges(table_defs, joins)

    customer_name = config.get("customer_name", "Demo")
    row_count = config.get("row_count", 10_000)
    years = config.get("years", 2)

    print(f"[rerun_ts_only] Customer: {customer_name}")
    print(f"  {len(table_defs)} tables, {len(joins)} joins")
    print(f"  Skipping Snowflake — using existing tables\n")

    result = run_pipeline(
        customer_name=customer_name,
        industry=config.get("industry", ""),
        focus=config.get("use_case_title", ""),
        row_count=row_count,
        table_defs=table_defs,
        joins=joins,
        skip_snowflake=True,
        charts=None,  # auto-generate from schema
        years=years,
        patterns=[],
    )

    print(f"\n[DONE]")
    print(f"  Model GUID     : {result['model_guid']}")
    print(f"  Liveboard GUID : {result['liveboard_guid']}")


if __name__ == "__main__":
    main()
