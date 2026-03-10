"""
Isolated test: generate a ThoughtSpot-ready star schema via Claude API.

Usage:
    python -m scripts.generate_schema
"""
import json

from dotenv import load_dotenv
import anthropic

load_dotenv(override=True)

# ── Hardcoded test input ──────────────────────────────────────────────────────
CUSTOMER = "Škoda Auto"
INDUSTRY = "výrobca automobilov"
DESCRIPTION = (
    "predaj áut za posledné 3 roky, 100k záznamov, "
    "zaujíma nás výkonnosť predaja podľa modelu, regiónu a typu dealera"
)

def generate_schema(customer: str, industry: str, description: str) -> dict:
    client = anthropic.Anthropic()

    prompt = (
        f"Customer: {customer}\n"
        f"Industry: {industry}\n"
        f"Description: {description}\n\n"
        "Design a star schema for ThoughtSpot analytics. "
        "Include one fact table and all necessary dimension tables. "
        "Use UPPER_SNAKE_CASE for all table and column names. "
        "For data_type choose from: INT64, VARCHAR, DOUBLE, DATE, BOOLEAN. "
        "For column_type use ATTRIBUTE for IDs/names/categories, "
        "MEASURE for numeric values that will be aggregated. "
        "Define all foreign-key relationships between the fact table and dimension tables."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=(
            "You are a data modelling expert specialising in analytical star schemas. "
            "Respond ONLY with a valid JSON object — no markdown, no explanation, no code block. "
            "The JSON must have exactly two keys: 'tables' (array) and 'relationships' (array). "
            "Each relationship object must have exactly these four keys: "
            "'fact_table', 'fact_column', 'dimension_table', 'dimension_column'."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            "Schema generation hit max_tokens limit — response was truncated. "
            "Increase max_tokens or simplify the schema request."
        )

    raw = response.content[0].text.strip()
    # Strip markdown code block if model adds it anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


if __name__ == "__main__":
    print(f"Customer  : {CUSTOMER}")
    print(f"Industry  : {INDUSTRY}")
    print(f"Description: {DESCRIPTION}")
    print("\nCalling Claude API...\n")

    schema = generate_schema(CUSTOMER, INDUSTRY, DESCRIPTION)

    print(json.dumps(schema, indent=2, ensure_ascii=False))
    print(f"\n— {len(schema['tables'])} tables, {len(schema['relationships'])} relationships —")
