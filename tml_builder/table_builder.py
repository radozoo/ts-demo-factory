"""Build ThoughtSpot Table TML from a TableDef dataclass."""
from __future__ import annotations

from thoughtspot_tml import Table
from schema.retail.tables import TableDef


def build_table_tml(table_def: TableDef, connection_name: str, settings_db: str, settings_schema: str) -> str:
    """
    Convert a TableDef into a validated TML YAML string.

    The string is round-tripped through thoughtspot_tml before returning.
    """
    col_lines = []
    for col in table_def.columns:
        col_lines += [
            f"  - name: {col.name}",
            f"    db_column_name: {col.name}",
            f"    properties:",
            f"      column_type: {col.column_type}",
            f"    db_column_properties:",
            f"      data_type: {col.ts_data_type}",
        ]

    raw = "\n".join([
        "table:",
        f"  name: {table_def.name}",
        f"  db: {settings_db}",
        f"  schema: {settings_schema}",
        f"  db_table: {table_def.name}",
        f"  connection:",
        f"    name: \"{connection_name}\"",
        f"  columns:",
        *col_lines,
        "",
    ])

    table_obj = Table.loads(raw)
    return table_obj.dumps()
