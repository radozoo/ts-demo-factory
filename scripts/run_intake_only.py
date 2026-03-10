"""
Run only the AI intake phase — no Snowflake, no ThoughtSpot.

Useful for testing the conversational flow and inspecting the output
before committing to a full pipeline run.

Usage:
    python -m scripts.run_intake_only
    python -m scripts.run_intake_only --save   # saves output to intake_output.json
"""
import argparse
import json
from dotenv import load_dotenv

load_dotenv(override=True)

from intake.intake_ai import IntakeEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="AI intake only — no Snowflake, no ThoughtSpot")
    parser.add_argument("--save", action="store_true", help="Save output to intake_output.json")
    args = parser.parse_args()

    engine = IntakeEngine()
    config = engine.run()

    print("\n" + "═" * 52)
    print("  Intake complete — pipeline config")
    print("═" * 52)
    print(f"  Customer : {config['customer_name']}")
    print(f"  Industry : {config['industry']}")
    print(f"  Use-case : {config.get('use_case_title', '—')}")
    print(f"  Tables   : {len(config['table_defs'])}")
    print(f"  Joins    : {len(config['joins'])}")
    charts = config.get("charts")
    print(f"  Charts   : {len(charts) if charts else 'auto-generate'}")

    if args.save:
        output = {
            "customer_name": config["customer_name"],
            "industry": config["industry"],
            "use_case_title": config.get("use_case_title", ""),
            "tables": [
                {
                    "name": td.name,
                    "columns": [
                        {"name": c.name, "type": c.ts_data_type, "kind": c.column_type}
                        for c in td.columns
                    ],
                }
                for td in config["table_defs"]
            ],
            "joins": config["joins"],
            "charts": config["charts"],
        }
        path = "intake_output.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n  Saved → {path}")


if __name__ == "__main__":
    main()
