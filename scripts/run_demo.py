"""
Final entry point for ts-demo-factory.

Usage:
    python -m scripts.run_demo                  # full run
    python -m scripts.run_demo --skip-snowflake # skip Snowflake, re-use cached schema
"""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from pipeline.orchestrator import run_pipeline
from scripts.intake import run_intake
from scripts.generate_schema import generate_schema
from scripts.schema_to_pipeline import json_to_table_defs, json_to_joins, align_fk_ranges

SCHEMA_CACHE = Path(__file__).parent.parent / "schema_cache.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-snowflake", action="store_true",
                        help="Skip Snowflake loading and re-use cached schema from previous run")
    args = parser.parse_args()

    if args.skip_snowflake and SCHEMA_CACHE.exists():
        cached = json.loads(SCHEMA_CACHE.read_text())
        schema = cached["schema"]
        config = cached["config"]
        print(f"\n[Schema] Loaded from cache ({SCHEMA_CACHE.name})")
        print(f"  Customer : {config['customer_name']}")
        print(f"  Industry : {config['industry']}")
    else:
        config = run_intake()
        print(f"\n[Schema] Generating star schema for '{config['customer_name']}'…")
        schema = generate_schema(
            customer=config["customer_name"],
            industry=config["industry"],
            description=config["focus_area"],
        )
        SCHEMA_CACHE.write_text(json.dumps({"schema": schema, "config": config}, ensure_ascii=False))

    table_defs = json_to_table_defs(schema)
    joins = json_to_joins(schema)
    align_fk_ranges(table_defs, joins)
    print(f"  ✓ {len(table_defs)} tables, {len(joins)} joins")
    if args.skip_snowflake:
        print("  ↷ Snowflake loading skipped")
        for td in table_defs:
            print(f"    • {td.name}")

    print(f"\nts-demo-factory — running pipeline for '{config['customer_name']}'")
    result = run_pipeline(
        customer_name=config["customer_name"],
        industry=config["industry"],
        focus=config["focus_area"],
        row_count=config["row_count"],
        table_defs=table_defs,
        joins=joins,
        skip_snowflake=args.skip_snowflake,
    )
    print("\n[DONE] Pipeline complete.")
    print(f"  Model GUID     : {result['model_guid']}")
    print(f"  Liveboard GUID : {result['liveboard_guid']}")


if __name__ == "__main__":
    main()