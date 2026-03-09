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

# ── Expected JSON structure ───────────────────────────────────────────────────
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["fact", "dimension"]},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "data_type": {"type": "string"},
                                "column_type": {
                                    "type": "string",
                                    "enum": ["ATTRIBUTE", "MEASURE"],
                                },
                            },
                            "required": ["name", "data_type", "column_type"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "type", "columns"],
                "additionalProperties": False,
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "on": {"type": "string"},
                },
                "required": ["from", "to", "on"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tables", "relationships"],
    "additionalProperties": False,
}


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
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=(
            "You are a data modelling expert specialising in analytical star schemas. "
            "Respond ONLY with a valid JSON object — no markdown, no explanation, no code block. "
            "The JSON must have exactly two keys: 'tables' (array) and 'relationships' (array)."
        ),
        messages=[{"role": "user", "content": prompt}],
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
