"""
AI-powered conversational demo setup.

Guides the user through 6 collaborative steps (customer context → domain → use-case →
schema → dataset config → liveboard), then runs the full pipeline.

Usage:
    python -m scripts.run_intake
    python -m scripts.run_intake --skip-snowflake
    python -m scripts.run_intake --row-count 100000   # overrides intake selection
"""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from intake.intake_ai import IntakeEngine
from scripts.schema_to_pipeline import align_fk_ranges
from pipeline.orchestrator import run_pipeline

SCHEMA_CACHE = Path(__file__).parent.parent / "schema_cache.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-guided ThoughtSpot demo builder")
    parser.add_argument(
        "--skip-snowflake", action="store_true",
        help="Skip Snowflake loading (tables must already exist and be registered in TS UI)"
    )
    parser.add_argument(
        "--row-count", type=int, default=None,
        help="Override row count from intake (default: use intake selection)"
    )
    args = parser.parse_args()

    engine = IntakeEngine()
    config = engine.run()  # blocks until all 6 steps complete

    table_defs = config["table_defs"]
    joins = config["joins"]
    align_fk_ranges(table_defs, joins)

    row_count = args.row_count if args.row_count is not None else config.get("row_count", 10_000)
    years = config.get("years", 2)
    patterns = config.get("patterns", [])

    print(f"\n[Pipeline] Starting for '{config['customer_name']}'…")
    print(f"  {len(table_defs)} tables, {len(joins)} joins")
    print(f"  {row_count:,} rows/table | {years} years history | patterns: {patterns or 'none'}")
    if args.skip_snowflake:
        print("  ↷ Snowflake loading skipped")

    result = run_pipeline(
        customer_name=config["customer_name"],
        industry=config["industry"],
        focus=config.get("use_case_title", ""),
        row_count=row_count,
        table_defs=table_defs,
        joins=joins,
        skip_snowflake=args.skip_snowflake,
        charts=config["charts"],
        years=years,
        patterns=patterns,
    )

    # Save schema cache for --skip-snowflake reruns
    schema = engine.state["schema"]
    cache = {
        "schema": schema,
        "config": {
            "customer_name": config["customer_name"],
            "industry": config["industry"],
            "use_case_title": config.get("use_case_title", ""),
            "row_count": row_count,
            "years": years,
        },
    }
    SCHEMA_CACHE.write_text(json.dumps(cache, indent=2))
    print(f"[Pipeline] Saved schema cache → {SCHEMA_CACHE.name}")

    print("\n[DONE] Pipeline complete.")
    print(f"  Model GUID     : {result['model_guid']}")
    print(f"  Liveboard GUID : {result['liveboard_guid']}")


if __name__ == "__main__":
    main()
