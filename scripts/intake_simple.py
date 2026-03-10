"""
CLI intake questionnaire — collects demo configuration before running the pipeline.

Usage (standalone):
    python -m scripts.intake

Returns a dict consumed by run_demo / run_pipeline.
"""
import questionary


INDUSTRIES = ["retail", "fintech", "healthcare", "logistics", "manufacturing"]

FOCUS_AREAS = [
    "sales performance",
    "inventory management",
    "customer analytics",
    "financial reporting",
    "operations",
]

TIME_PERIODS = ["last 12 months", "last 24 months", "last 36 months"]

ROW_COUNTS = {
    "small  (10k)":  10_000,
    "medium (100k)": 100_000,
    "large  (500k)": 500_000,
}


def run_intake() -> dict:
    """Interactively collect demo parameters and return them as a dict."""
    print("\n=== ts-demo-factory — Demo Setup ===\n")

    customer_name = questionary.text(
        "Customer name:",
        validate=lambda v: bool(v.strip()) or "Customer name cannot be empty.",
    ).ask()

    industry = questionary.select(
        "Industry:",
        choices=INDUSTRIES,
    ).ask()

    focus_area = questionary.select(
        "Focus area:",
        choices=FOCUS_AREAS,
    ).ask()

    time_period = questionary.select(
        "Time period of data:",
        choices=TIME_PERIODS,
    ).ask()

    row_count_label = questionary.select(
        "Number of records per table:",
        choices=list(ROW_COUNTS.keys()),
    ).ask()

    special_requirements = questionary.text(
        "Special requirements (optional, press Enter to skip):",
    ).ask()

    return {
        "customer_name": customer_name.strip(),
        "industry": industry,
        "focus_area": focus_area,
        "time_period": time_period,
        "row_count": ROW_COUNTS[row_count_label],
        "special_requirements": special_requirements.strip() if special_requirements else "",
    }


if __name__ == "__main__":
    import json
    result = run_intake()
    print("\nCollected configuration:")
    print(json.dumps(result, indent=2))
