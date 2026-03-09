"""
Final entry point for ts-demo-factory.

Usage:
    python -m scripts.run_demo --customer "Acme Corp" --industry retail --focus EMEA
"""
import argparse
from pipeline.orchestrator import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ts-demo-factory pipeline")
    parser.add_argument("--customer", required=True, help="Customer name")
    parser.add_argument("--industry", default="retail", help="Industry (default: retail)")
    parser.add_argument("--focus", default="", help="Focus area (e.g. EMEA, Q1 2025)")
    parser.add_argument("--rows", type=int, default=10_000, help="Rows per table (default: 10000)")
    args = parser.parse_args()

    print(f"\nts-demo-factory — running pipeline for '{args.customer}'")
    result = run_pipeline(
        customer_name=args.customer,
        industry=args.industry,
        focus=args.focus,
        row_count=args.rows,
    )
    print("\n[DONE] Pipeline complete.")
    print(f"  Worksheet GUID : {result['model_guid']}")
    print(f"  Liveboard GUID : {result['liveboard_guid']}")


if __name__ == "__main__":
    main()
