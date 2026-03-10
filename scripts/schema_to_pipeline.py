"""
Translate the JSON schema produced by generate_schema.py into
TableDef / ColumnDef objects that the existing pipeline understands.

JSON relationship format (as Claude returns):
  {"fact_table": "FACT_X", "fact_column": "DIM_ID",
   "dimension_table": "DIM_Y", "dimension_column": "DIM_ID"}
"""
from __future__ import annotations

from schema.retail.tables import ColumnDef, TableDef


# ── Type mappings ─────────────────────────────────────────────────────────────

_DB_TYPE: dict[str, str] = {
    "INT64":   "NUMBER(18,0)",
    "DOUBLE":  "NUMBER(18,2)",
    "VARCHAR": "VARCHAR(200)",
    "DATE":    "DATE",
    "BOOLEAN": "VARCHAR(5)",  # TS doesn't support BOOLEAN — store as 'true'/'false'
}

# ── Faker heuristics ──────────────────────────────────────────────────────────

def _faker_for(col_name: str, ts_data_type: str, column_type: str) -> tuple[str, dict]:
    """
    Return (faker_method, faker_kwargs) for a column.
    Heuristics are based on column name patterns + data type.
    """
    n = col_name.upper()

    # --- BOOLEAN (stored as VARCHAR 'true'/'false') ---
    if ts_data_type == "BOOLEAN" or n.startswith("IS_") or n.startswith("HAS_"):
        return "random_element", {"elements": ["true", "false"]}

    # --- Foreign-key / surrogate IDs (must be before DATE to avoid DATE_KEY mismatch) ---
    if n.endswith("_ID") or n.endswith("_KEY") or n == "ID":
        return "random_int", {"min": 1, "max": 1_000}

    # --- DATE ---
    if ts_data_type == "DATE" or n.endswith("_DATE") or n.startswith("DATE"):
        return "date_between", {"start_date": "-3y", "end_date": "today"}

    # --- MEASUREs ---
    if column_type == "MEASURE":
        if ts_data_type == "INT64":
            if any(x in n for x in ("QUANTITY", "QTY", "COUNT", "UNITS", "SOLD")):
                return "random_int", {"min": 1, "max": 500}
            if any(x in n for x in ("YEAR",)):
                return "random_int", {"min": 2000, "max": 2024}
            return "random_int", {"min": 1, "max": 10_000}
        # DOUBLE measures → monetary / ratio
        return "pydecimal", {"left_digits": 6, "right_digits": 2, "positive": True}

    # --- ATTRIBUTEs by name pattern ---
    if any(x in n for x in ("YEAR",)):
        return "random_int", {"min": 2000, "max": 2024}

    if any(x in n for x in ("NAME",)):
        if any(x in n for x in ("COMPANY", "DEALER", "BRAND", "STORE", "ORG")):
            return "company", {}
        if any(x in n for x in ("PRODUCT", "MODEL", "ITEM")):
            return "catch_phrase", {}
        return "name", {}

    if any(x in n for x in ("CITY",)):
        return "city", {}

    if any(x in n for x in ("COUNTRY",)):
        return "country", {}

    if any(x in n for x in ("CONTINENT",)):
        return "random_element", {"elements": ["Europe", "Asia", "Americas", "Africa", "Oceania"]}

    if any(x in n for x in ("REGION",)):
        return "random_element", {"elements": ["North", "South", "East", "West", "Central"]}

    if any(x in n for x in ("STATUS",)):
        return "random_element", {"elements": ["Active", "Inactive", "Pending", "Closed"]}

    if any(x in n for x in ("TIER", "LEVEL", "CLASS")):
        return "random_element", {"elements": ["Bronze", "Silver", "Gold", "Platinum"]}

    if any(x in n for x in ("SIZE",)):
        return "random_element", {"elements": ["Small", "Medium", "Large", "Extra Large"]}

    if any(x in n for x in ("TYPE", "CATEGORY")):
        return "random_element", {"elements": ["Standard", "Premium", "Basic", "Enterprise"]}

    if any(x in n for x in ("CURRENCY",)):
        return "currency_code", {}

    if any(x in n for x in ("CODE",)):
        return "lexify", {"text": "??-####"}

    if ts_data_type == "INT64":
        return "random_int", {"min": 1, "max": 9_999}

    # VARCHAR fallback
    return "catch_phrase", {}


# ── Main translation function ─────────────────────────────────────────────────

def json_to_table_defs(schema: dict) -> list[TableDef]:
    """
    Convert a JSON schema dict (from generate_schema.py) to a list of TableDef objects.

    The first column of a fact table with PK-like name is marked is_pk=True.
    Dimension table first column (usually *_ID) is also marked is_pk=True.
    """
    table_defs: list[TableDef] = []

    for tbl in schema["tables"]:
        tbl_name = tbl.get("name") or tbl.get("table_name") or tbl.get("table", "")
        if not tbl_name:
            raise ValueError(f"Table entry has no name key. Keys: {list(tbl.keys())}")
        tbl = {**tbl, "name": tbl_name}
        columns: list[ColumnDef] = []
        is_first = True

        for col in tbl["columns"]:
            name     = col.get("name") or col.get("column_name") or col.get("col_name", "")
            ts_dtype = col.get("data_type") or col.get("type", "VARCHAR")
            if ts_dtype == "BOOLEAN":
                ts_dtype = "VARCHAR"  # TS doesn't support BOOLEAN
            col_type = col.get("column_type") or col.get("kind", "ATTRIBUTE")
            if not name:
                raise ValueError(f"Column in table '{tbl['name']}' missing name key. Keys: {list(col.keys())}")
            db_type     = _DB_TYPE.get(ts_dtype, "VARCHAR(200)")
            faker_m, faker_kw = _faker_for(name, ts_dtype, col_type)

            # Mark first column of each table as PK (convention: it's the ID)
            is_pk = is_first and name.endswith("_ID")
            is_first = False

            columns.append(ColumnDef(
                name=name,
                db_type=db_type,
                ts_data_type=ts_dtype,
                column_type=col_type,
                faker_method=faker_m,
                faker_kwargs=faker_kw,
                is_pk=is_pk,
            ))

        tbl_type = tbl.get("type", "fact" if "FACT" in tbl_name.upper() else "dimension")
        table_defs.append(TableDef(
            name=tbl_name,
            description=f"{tbl_type.capitalize()} table — auto-generated",
            columns=columns,
        ))

    return table_defs


def json_to_joins(schema: dict) -> list[dict]:
    """
    Convert relationships array to a list of join specs for the model builder.

    Handles two formats Claude may return:
      A) {"fact_table":..., "fact_column":..., "dimension_table":..., "dimension_column":...}
      B) {"from":..., "to":..., "on":...}  e.g. "SALES_FACT.STORE_ID = DIM_STORE.STORE_ID"

    Output format:
      [{"fact": "FACT_X", "dim": "DIM_Y", "fact_col": "DIM_ID", "dim_col": "DIM_ID"}]
    """
    joins = []
    for rel in schema.get("relationships", []):
        if "fact_table" in rel:
            joins.append({
                "fact":     rel["fact_table"],
                "dim":      rel["dimension_table"],
                "fact_col": rel["fact_column"],
                "dim_col":  rel["dimension_column"],
            })
        elif "from_table" in rel:
            joins.append({
                "fact":     rel["from_table"],
                "dim":      rel["to_table"],
                "fact_col": rel["from_column"],
                "dim_col":  rel["to_column"],
            })
        elif "from" in rel and "on" in rel:
            # Parse "TABLE_A.COL = TABLE_B.COL" or just use table names + shared col
            on = rel["on"].replace(" ", "")
            parts = on.split("=")
            left_t, left_c  = parts[0].split(".") if "." in parts[0] else (rel["from"], parts[0])
            right_t, right_c = parts[1].split(".") if "." in parts[1] else (rel["to"],  parts[1])
            joins.append({
                "fact":     left_t,
                "dim":      right_t,
                "fact_col": left_c,
                "dim_col":  right_c,
            })
        else:
            print(f"  ⚠ Unknown relationship format — skipping: {list(rel.keys())}")
            continue

    if not joins and schema.get("relationships"):
        raise RuntimeError(
            f"[Schema] All {len(schema['relationships'])} relationships had unknown format — "
            "no joins built. Check Claude API output."
        )
    return joins




# ── FK range alignment ─────────────────────────────────────────────────────────

def align_fk_ranges(table_defs: list[TableDef], joins: list[dict]) -> None:
    """
    Ensure every fact FK column uses the same ID range as the corresponding dim PK column.

    With random_int, both sides must use the same max so LEFT JOINs produce matches.
    Mutates table_defs in-place (replaces ColumnDef in the columns list).
    """
    import dataclasses
    td_map = {td.name: td for td in table_defs}

    for join in joins:
        fact_td = td_map.get(join["fact"])
        dim_td = td_map.get(join["dim"])
        if not fact_td or not dim_td:
            continue

        dim_pk_col = next(
            (c for c in dim_td.columns if c.name == join["dim_col"] and c.faker_method == "random_int"),
            None,
        )
        if dim_pk_col is None:
            continue
        dim_max = dim_pk_col.faker_kwargs.get("max", 1_000)

        for i, col in enumerate(fact_td.columns):
            if col.name == join["fact_col"] and col.faker_method == "random_int":
                fact_td.columns[i] = dataclasses.replace(
                    col, faker_kwargs={**col.faker_kwargs, "max": dim_max}
                )
                break

# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from scripts.generate_schema import generate_schema, CUSTOMER, INDUSTRY, DESCRIPTION

    print(f"Generating schema for: {CUSTOMER}\n")
    schema = generate_schema(CUSTOMER, INDUSTRY, DESCRIPTION)

    table_defs = json_to_table_defs(schema)
    joins      = json_to_joins(schema)

    print(f"=== {len(table_defs)} TableDef objects ===\n")
    for td in table_defs:
        cols      = td.columns
        measures  = [c for c in cols if c.column_type == "MEASURE"]
        attrs     = [c for c in cols if c.column_type == "ATTRIBUTE"]
        pks       = [c for c in cols if c.is_pk]
        print(f"  {td.name}")
        print(f"    columns   : {len(cols)}  (ATTRIBUTEs: {len(attrs)}, MEASUREs: {len(measures)}, PKs: {len(pks)})")
        for c in cols:
            pk_flag = " [PK]" if c.is_pk else ""
            print(f"      {c.name:<30} {c.ts_data_type:<8} {c.column_type:<10} faker={c.faker_method}{pk_flag}")
        print()

    print(f"=== {len(joins)} Joins ===\n")
    for j in joins:
        print(f"  {j['fact']}.{j['fact_col']} → {j['dim']}.{j['dim_col']}")
