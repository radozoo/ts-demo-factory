"""Build ThoughtSpot Table TML from a TableDef dataclass."""
from __future__ import annotations

import textwrap
from thoughtspot_tml import Table
from schema.retail.tables import TableDef


def build_table_tml(table_def: TableDef, connection_name: str) -> str:
    """
    Convert a TableDef into a validated TML YAML string.

    The string is round-tripped through thoughtspot_tml before returning.
    """
    columns_yaml = "\n".join(
        textwrap.dedent(f"""\
            - name: {col.name}
              db_column_name: {col.name}
              properties:
                column_type: {col.column_type}
              db:
                column_data_type: {col.ts_data_type}
        """).rstrip()
        for col in table_def.columns
    )

    raw = textwrap.dedent(f"""\
        table:
          name: {table_def.name}
          db_table: {table_def.name}
          connection:
            name: "{connection_name}"
          columns:
        {textwrap.indent(columns_yaml, "    ")}
    """)

    table_obj = Table.loads(raw)
    return table_obj.dumps()
