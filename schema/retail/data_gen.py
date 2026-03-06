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


def generate_rows(table: TableDef, n: int) -> list[dict]:
    """Generate *n* rows for *table* as list of column_name → value dicts."""
    rows = []
    for _ in range(n):
        row = {col.name: _call_faker(col) for col in table.columns}
        rows.append(row)
    return rows
