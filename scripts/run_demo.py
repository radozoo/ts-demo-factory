"""
Final entry point for ts-demo-factory.

Usage:
    python -m scripts.run_demo
"""
from pipeline.orchestrator import run_pipeline
from scripts.intake import run_intake


def main() -> None:
    config = run_intake()

    print(f"\nts-demo-factory — running pipeline for '{config['customer_name']}'")
    result = run_pipeline(
        customer_name=config["customer_name"],
        industry=config["industry"],
        focus=config["focus_area"],
        row_count=config["row_count"],
    )
    print("\n[DONE] Pipeline complete.")
    print(f"  Worksheet GUID : {result['model_guid']}")
    print(f"  Liveboard GUID : {result['liveboard_guid']}")


if __name__ == "__main__":
    main()
