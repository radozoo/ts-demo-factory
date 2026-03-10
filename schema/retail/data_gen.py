"""Faker-based row generator driven by ColumnDef metadata."""
from __future__ import annotations

import operator
from faker import Faker
from schema.retail.tables import TableDef, ColumnDef

fake = Faker()
Faker.seed(42)


def _call_faker(col: ColumnDef):
    """Resolve faker_method on the Faker instance and call with faker_kwargs."""
    method = operator.attrgetter(col.faker_method)(fake)
    value = method(**col.faker_kwargs)
    # Ensure Decimal types become floats for Snowflake connector compatibility
    try:
        from decimal import Decimal
        if isinstance(value, Decimal):
            return float(value)
    except ImportError:
        pass
    return value


def _apply_patterns(row: dict, table: TableDef, patterns: set[str]) -> dict:
    """Apply data patterns to a generated row. Returns a (possibly modified) copy."""
    if not patterns:
        return row

    multiplier = 1.0

    # Seasonality: boost measures ~60% in spring/summer months (March–August)
    if "seasonality" in patterns:
        date_col = next((c for c in table.columns if c.ts_data_type == "DATE"), None)
        if date_col:
            dv = row.get(date_col.name)
            if hasattr(dv, "month") and dv.month in (3, 4, 5, 6, 7, 8):
                multiplier *= 1.6

    # Anomalies: 2% of rows get a 5× measure spike
    if "anomalies" in patterns and fake.random_int(1, 100) <= 2:
        multiplier *= 5.0

    if multiplier == 1.0:
        return row

    row = dict(row)
    for col in table.columns:
        if col.column_type != "MEASURE":
            continue
        v = row.get(col.name)
        if isinstance(v, float):
            row[col.name] = v * multiplier
        elif isinstance(v, int):
            row[col.name] = max(1, int(round(v * multiplier)))

    return row


def generate_rows(
    table: TableDef,
    n: int,
    years: int = 2,
    patterns: list[str] | None = None,
) -> list[dict]:
    """Generate *n* rows for *table* as list of column_name → value dicts.

    Args:
        table:    TableDef to generate rows for.
        n:        Number of rows.
        years:    How many years back DATE columns should span (default 2).
        patterns: List of canonical pattern IDs to inject (e.g. ["seasonality", "anomalies"]).
    """
    pat = set(patterns or [])
    date_start = f"-{years}y"
    rows = []

    for _ in range(n):
        row = {}
        for col in table.columns:
            # Override date range based on the years parameter
            if col.faker_method == "date_between":
                value = fake.date_between(start_date=date_start, end_date="today")
            else:
                value = _call_faker(col)
            row[col.name] = value

        row = _apply_patterns(row, table, pat)
        rows.append(row)

    return rows
