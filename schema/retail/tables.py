"""Retail/FMCG schema definitions — Phase 1 (hard-coded)."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ColumnDef:
    name: str                    # column name in Snowflake + TML
    db_type: str                 # Snowflake SQL type, e.g. "NUMBER(18,2)"
    ts_data_type: str            # ThoughtSpot db_column_data_type, e.g. "DOUBLE"
    column_type: str             # ThoughtSpot column_type: "ATTRIBUTE" or "MEASURE"
    faker_method: str            # dotted method on Faker instance, e.g. "random_int"
    faker_kwargs: dict = field(default_factory=dict)
    is_pk: bool = False


@dataclass
class TableDef:
    name: str                    # Snowflake table name
    columns: list[ColumnDef]
    description: str = ""


# ── SALES_FACT ────────────────────────────────────────────────────────────────
SALES_FACT = TableDef(
    name="SALES_FACT",
    description="Transactional fact table — one row per sales transaction",
    columns=[
        ColumnDef("SALE_ID",     "NUMBER(18,0)", "INT64",  "ATTRIBUTE", "random_int", {"min": 1, "max": 9_999_999}, is_pk=True),
        ColumnDef("DATE",        "DATE",          "DATE",   "ATTRIBUTE", "date_between", {"start_date": "-2y", "end_date": "today"}),
        ColumnDef("PRODUCT_ID",  "NUMBER(10,0)", "INT64",  "ATTRIBUTE", "random_int", {"min": 1, "max": 500}),
        ColumnDef("STORE_ID",    "NUMBER(10,0)", "INT64",  "ATTRIBUTE", "random_int", {"min": 1, "max": 100}),
        ColumnDef("CUSTOMER_ID", "NUMBER(10,0)", "INT64",  "ATTRIBUTE", "random_int", {"min": 1, "max": 50_000}),
        ColumnDef("QUANTITY",    "NUMBER(10,0)", "INT64",  "MEASURE",   "random_int", {"min": 1, "max": 50}),
        ColumnDef("REVENUE",     "NUMBER(18,2)", "DOUBLE", "MEASURE",   "pydecimal",  {"left_digits": 5, "right_digits": 2, "positive": True}),
        ColumnDef("COST",        "NUMBER(18,2)", "DOUBLE", "MEASURE",   "pydecimal",  {"left_digits": 5, "right_digits": 2, "positive": True}),
        ColumnDef("DISCOUNT",    "NUMBER(5,2)",  "DOUBLE", "MEASURE",   "pydecimal",  {"left_digits": 2, "right_digits": 2, "positive": True, "max_value": 50}),
    ],
)

# ── DIM_STORE ─────────────────────────────────────────────────────────────────
DIM_STORE = TableDef(
    name="DIM_STORE",
    description="Store dimension",
    columns=[
        ColumnDef("STORE_ID",       "NUMBER(10,0)", "INT64",   "ATTRIBUTE", "random_int", {"min": 1, "max": 100}, is_pk=True),
        ColumnDef("STORE_NAME",     "VARCHAR(200)", "VARCHAR", "ATTRIBUTE", "company"),
        ColumnDef("REGION",         "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["North", "South", "East", "West", "Central"]}),
        ColumnDef("CITY",           "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "city"),
        ColumnDef("COUNTRY",        "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "country"),
        ColumnDef("STORE_SIZE_SQFT","NUMBER(10,0)", "INT64",   "MEASURE",   "random_int", {"min": 500, "max": 50_000}),
    ],
)

# ── DIM_PRODUCT ───────────────────────────────────────────────────────────────
DIM_PRODUCT = TableDef(
    name="DIM_PRODUCT",
    description="Product dimension",
    columns=[
        ColumnDef("PRODUCT_ID",   "NUMBER(10,0)", "INT64",   "ATTRIBUTE", "random_int", {"min": 1, "max": 500}, is_pk=True),
        ColumnDef("PRODUCT_NAME", "VARCHAR(200)", "VARCHAR", "ATTRIBUTE", "catch_phrase"),
        ColumnDef("CATEGORY",     "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["Beverages", "Dairy", "Bakery", "Snacks", "Produce", "Meat", "Frozen", "Personal Care"]}),
        ColumnDef("SUBCATEGORY",  "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["Premium", "Standard", "Budget", "Organic", "Value"]}),
        ColumnDef("BRAND",        "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "company"),
        ColumnDef("UNIT_PRICE",   "NUMBER(10,2)", "DOUBLE",  "MEASURE",   "pydecimal", {"left_digits": 3, "right_digits": 2, "positive": True}),
    ],
)

# ── DIM_CUSTOMER ──────────────────────────────────────────────────────────────
DIM_CUSTOMER = TableDef(
    name="DIM_CUSTOMER",
    description="Customer dimension",
    columns=[
        ColumnDef("CUSTOMER_ID",   "NUMBER(10,0)", "INT64",   "ATTRIBUTE", "random_int", {"min": 1, "max": 50_000}, is_pk=True),
        ColumnDef("CUSTOMER_NAME", "VARCHAR(200)", "VARCHAR", "ATTRIBUTE", "name"),
        ColumnDef("LOYALTY_TIER",  "VARCHAR(50)",  "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["Bronze", "Silver", "Gold", "Platinum"]}),
        ColumnDef("AGE_GROUP",     "VARCHAR(50)",  "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]}),
        ColumnDef("GENDER",        "VARCHAR(20)",  "VARCHAR", "ATTRIBUTE", "random_element", {"elements": ["Male", "Female", "Non-binary", "Prefer not to say"]}),
        ColumnDef("CITY",          "VARCHAR(100)", "VARCHAR", "ATTRIBUTE", "city"),
    ],
)

# ── Registry ──────────────────────────────────────────────────────────────────
ALL_TABLES: list[TableDef] = [DIM_STORE, DIM_PRODUCT, DIM_CUSTOMER, SALES_FACT]
