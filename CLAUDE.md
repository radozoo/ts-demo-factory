# ts-demo-factory — CLAUDE.md

## Project purpose
Automated creation of ThoughtSpot demo environments for customers.
Input: customer name, industry, focus area.
Output: dummy data in Snowflake + TML objects (Tables, Model, Liveboard) imported into ThoughtSpot via REST API v2.

Phase 1 is Retail/FMCG schema (hard-coded, no LLM).

---

## Architecture overview

```
config/settings.py               ← all env vars, loaded once via Settings.from_env()
ts_client/auth.py                ← ThoughtSpotAuth: Bearer token with caching + auto re-auth
ts_client/tml_api.py             ← TMLClient: import_tml(), export_tml(), delete_by_name()
schema/retail/tables.py          ← TableDef + ColumnDef dataclasses (4 tables)
schema/retail/data_gen.py        ← Faker generators driven by ColumnDef
tml_builder/table_builder.py     ← TableDef → thoughtspot_tml.Table → YAML
tml_builder/model_builder.py     ← Jinja2 template → thoughtspot_tml.Model → YAML
tml_builder/liveboard_builder.py ← Jinja2 template → thoughtspot_tml.Liveboard → YAML
snowflake_client/loader.py       ← DDL from TableDef, bulk INSERT (RSA key pair auth)
pipeline/orchestrator.py         ← runs steps in order, threads GUIDs between steps
scripts/step1_ts_api_test.py     ← smoke test (Gate 1)
scripts/run_demo.py              ← final entry point
```

---

## Key invariants

### TML construction
- `thoughtspot_tml` dataclasses = primary method for Tables
- Jinja2 templates = for complex YAML (Models, Liveboards)
- **Every TML string MUST pass `.loads()/.dumps()` before any API call**

### Import order (GUID dependency)
```
Tables → [get table GUIDs] → Model → [get model GUID] → Liveboard
```

### Cleanup before reimport
- `create_new_on_import: True` always creates a new object → duplicates accumulate
- Always call `client.delete_by_name([lb_name], "LIVEBOARD")` then `client.delete_by_name([model_name], "LOGICAL_TABLE")` before reimporting Model + Liveboard
- Delete liveboard FIRST (depends on model), then model

### Auth
- Always Bearer token (never session cookies)
- Token cached with expiry tracking in `ThoughtSpotAuth`
- 401 response → automatic single re-auth attempt

### Snowflake auth
- RSA key pair (`.p8` file), DER format via `cryptography` library
- Env var: `SNOWFLAKE_PRIVATE_KEY_PATH`
- `load_dotenv(override=True)` required to prevent stale shell env vars

### Connection name
- Stored in `.env` as `TS_CONNECTION_NAME` — never hardcoded
- Default: `"Revolt Snowflake Playground"`

---

## Retail schema (Phase 1) — 4 tables

| Table | Key columns |
|-------|-------------|
| `SALES_FACT` | SALE_ID, DATE, PRODUCT_ID, STORE_ID, CUSTOMER_ID, QUANTITY, REVENUE, COST, DISCOUNT |
| `DIM_STORE` | STORE_ID, STORE_NAME, REGION, CITY, COUNTRY, STORE_SIZE_SQFT |
| `DIM_PRODUCT` | PRODUCT_ID, PRODUCT_NAME, CATEGORY, SUBCATEGORY, BRAND, UNIT_PRICE |
| `DIM_CUSTOMER` | CUSTOMER_ID, CUSTOMER_NAME, LOYALTY_TIER, AGE_GROUP, GENDER, CITY |

---

## Running

```bash
# Setup (once)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env

# Step 1 smoke test
python -m scripts.step1_ts_api_test

# Full pipeline
python -m scripts.run_demo --customer "Acme Corp" --industry retail --focus EMEA
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `TS_HOST` | e.g. `https://myorg.thoughtspot.cloud` |
| `TS_USERNAME` | ThoughtSpot login email |
| `TS_PASSWORD` | ThoughtSpot password |
| `TS_ORG_ID` | Org ID (default `0`) |
| `TS_CONNECTION_NAME` | Name of Snowflake connection in TS |
| `SF_ACCOUNT` | Snowflake account identifier |
| `SF_USER` | Snowflake username |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | Path to RSA `.p8` private key file |
| `SF_DATABASE` | Target database |
| `SF_SCHEMA` | Target schema |
| `SF_WAREHOUSE` | Virtual warehouse |
| `SF_ROLE` | Snowflake role |

---

## Development conventions
- Python 3.11+
- No global mutable state — pass `Settings` and `ThoughtSpotAuth` instances explicitly
- All API errors raise `RuntimeError` with status code + truncated body
- Scripts runnable as modules: `python -m scripts.run_demo`

---

## Status (updated 2026-03-09)

### Phase 1 — COMPLETE ✓
Full pipeline works end-to-end:
1. Creates 4 Snowflake tables + loads 10K rows each (40K total)
2. Imports Table TMLs → gets table GUIDs
3. Cleans up old Model + Liveboard by name
4. Imports Model TML → gets model GUID
5. Imports Liveboard TML → renders charts correctly

### Environment (dev)
- TS instance: `https://techpartners.thoughtspot.cloud`
- SF account: `jxgpfar-revolt_partner` | DB: `_REVOLT_ANALYTICS_DEV` | Schema: `RADO`
- TS connection ID: `76372876-5a62-4016-b4fa-84499feb6be5` (Revolt Snowflake Playground)
- TS connection SF role: `_R_DEVELOPER` | warehouse: `HACKATHON_WH`
- `venv/` exists and is fully installed

---

## Critical TML gotchas

### Model (not Worksheet)
ThoughtSpot deprecated Worksheets — use `model:` top-level key.
- `model_tables:` with inline `joins:` per dimension table
- Quote `"with":` and `"on":` — YAML reserved words
- `columns:` with `column_id: TABLE_NAME::COLUMN_NAME` format
- `aggregation: AVERAGE` (not `AVG`)

```yaml
model:
  name: My_Model
  model_tables:
    - name: SALES_FACT
      fqn: <guid>
    - name: DIM_STORE
      fqn: <guid>
      joins:
        - "with": SALES_FACT
          "on": "[SALES_FACT::STORE_ID] = [DIM_STORE::STORE_ID]"
          type: LEFT_OUTER
          cardinality: MANY_TO_ONE
  columns:
    - name: Revenue
      column_id: SALES_FACT::REVENUE
      properties:
        column_type: MEASURE
        aggregation: SUM
```

### Liveboard: chart_columns + axis_configs are REQUIRED
Without them TS throws `Index 0 out of bounds for length 0` and the liveboard shows "Error in loading data".

Each visualization must include:
```yaml
chart:
  type: BAR
  chart_columns:
    - column_id: Region
    - column_id: Total Revenue
  axis_configs:
    - x:
        - Region
      y:
        - Total Revenue
  client_state: ""
```

### Column name resolution (TS resolves at import time)
Search query column names differ from model column names:
- `[Revenue]` (SUM) → `Total Revenue`
- `[Quantity]` (SUM) → `Total Quantity`
- `average [Discount]` → `Average Discount`
- `[Date].monthly` → `Month(Date)`
- Attribute columns keep their exact model name

Use resolved names in `answer_columns`, `table_columns`, `chart_columns`, `ordered_column_ids`.

### Table TML column format (thoughtspot_tml v2.4.2)
```yaml
columns:
  - name: ID
    db_column_name: ID
    properties:
      column_type: ATTRIBUTE
    db_column_properties:
      data_type: INT64
```
Table-level TML requires `db` and `schema` fields:
```yaml
table:
  name: MY_TABLE
  db: _REVOLT_ANALYTICS_DEV
  schema: RADO
  db_table: MY_TABLE
  connection:
    name: "Revolt Snowflake Playground"
```

### Delete endpoint quirk
`POST /api/rest/2.0/metadata/delete` returns 204 (empty body) — do NOT use `_post()` for it, use `requests.post()` directly.

### TS connection/update API — BROKEN for registering new tables
- `POST /api/rest/2.0/connection/update` → always 500 or silently does nothing
- **Workaround:** after creating tables in Snowflake, register them in TS connection via
  **ThoughtSpot UI** (Data → Add data → Browse connection → select tables)
- Tables registered: SALES_FACT, DIM_STORE, DIM_PRODUCT, DIM_CUSTOMER (all in `_REVOLT_ANALYTICS_DEV.RADO`)

---

## Phase 2 — next steps
- Parameterize industry (currently hard-coded to retail)
- Add LLM-driven schema/query generation
- Support multiple industries (fintech, healthcare, etc.)
