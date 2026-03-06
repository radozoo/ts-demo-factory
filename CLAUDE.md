# ts-demo-factory — CLAUDE.md

## Project purpose
Automated creation of ThoughtSpot demo environments for customers.
Input: customer name, industry, focus area.
Output: dummy data in Snowflake + TML objects (Tables, Worksheet, Liveboard) imported into ThoughtSpot via REST API v2.

Phase 1 is Retail/FMCG schema (hard-coded, no LLM).

---

## Architecture overview

```
config/settings.py          ← all env vars, loaded once via Settings.from_env()
ts_client/auth.py           ← ThoughtSpotAuth: Bearer token with caching + auto re-auth
ts_client/tml_api.py        ← TMLClient: import_tml(), export_tml()
schema/retail/tables.py     ← TableDef + ColumnDef dataclasses (4 tables)
schema/retail/data_gen.py   ← Faker generators driven by ColumnDef
tml_builder/table_builder.py     ← TableDef → thoughtspot_tml.Table → YAML
tml_builder/worksheet_builder.py ← Jinja2 template → thoughtspot_tml.Worksheet
tml_builder/liveboard_builder.py ← Jinja2 template → thoughtspot_tml.Liveboard
snowflake_client/loader.py  ← DDL from TableDef, bulk INSERT
pipeline/orchestrator.py    ← runs steps in order, threads GUIDs between steps
scripts/step1_ts_api_test.py ← smoke test (Gate 1)
scripts/run_demo.py         ← final entry point
```

---

## Key invariants

### TML construction
- `thoughtspot_tml` dataclasses = primary method for Tables
- Jinja2 templates = for complex YAML (Worksheets, Liveboards)
- **Every TML string MUST pass `.loads()/.dumps()` before any API call**

### Import order (GUID dependency)
```
Tables → [get table GUIDs] → Worksheet → [get ws GUID] → Liveboard
```

### Auth
- Always Bearer token (never session cookies)
- Token cached with expiry tracking in `ThoughtSpotAuth`
- 401 response → automatic single re-auth attempt

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

# Full pipeline (Phase 2+)
python -m scripts.run_demo
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
| `SF_PASSWORD` | Snowflake password |
| `SF_DATABASE` | Target database |
| `SF_SCHEMA` | Target schema |
| `SF_WAREHOUSE` | Virtual warehouse |
| `SF_ROLE` | Snowflake role |

---

## Development conventions
- Python 3.11+
- No global mutable state — pass `Settings` and `ThoughtSpotAuth` instances explicitly
- All API errors raise `RuntimeError` with status code + truncated body
- Scripts runnable as modules: `python -m scripts.step1_ts_api_test`

---

## Status & known issues (updated 2026-03-05)

### Gate 1 — COMPLETE ✓
`python -m scripts.step1_ts_api_test` passes cleanly.

### Environment (dev)
- TS instance: `https://techpartners.thoughtspot.cloud`
- SF account: `jxgpfar-revolt_partner` | DB: `_REVOLT_ANALYTICS_DEV` | Schema: `RADO`
- TS connection ID: `76372876-5a62-4016-b4fa-84499feb6be5` (Revolt Snowflake Playground)
- TS connection SF role: `_R_DEVELOPER` | warehouse: `HACKATHON_WH`
- `venv/` exists and is fully installed

### TML column format (thoughtspot_tml v2.4.2)
Correct column structure — use `db_column_properties.data_type`, NOT `db.column_data_type`:
```yaml
columns:
  - name: ID
    db_column_name: ID
    properties:
      column_type: ATTRIBUTE
    db_column_properties:
      data_type: INT64
```
Table-level TML requires `db` and `schema` fields (not just `db_table`):
```yaml
table:
  name: MY_TABLE
  db: _REVOLT_ANALYTICS_DEV
  schema: RADO
  db_table: MY_TABLE
  connection:
    name: "Revolt Snowflake Playground"
```

### TS connection/update API — BROKEN for registering new tables
- `POST /api/rest/2.0/connection/update` with `data_warehouse_config` → always 500
- Without `data_warehouse_config` → 204 but silently does nothing
- **Consequence:** cannot register a brand-new Snowflake table into TS via REST API
- **Workaround for smoke test:** export existing registered table TML → VALIDATE_ONLY re-import
- **Workaround for Phase 2:** after creating tables in Snowflake, must register them in TS
  connection via **ThoughtSpot UI** (Data → Add data → Browse connection → select tables)
  before running TML import via API

### Tables already registered in TS connection
DIM_CHANNEL, DIM_PROGRAM, DIM_TIME, DIM_DEMO, DIM_REGION (all in `_REVOLT_ANALYTICS_DEV.RADO`)

### Phase 2 — next steps
1. Create 4 retail tables in Snowflake (`snowflake_client/loader.py`)
2. Register them in TS connection via UI (one-time manual step)
3. Generate fake data via `schema/retail/data_gen.py`
4. Build TML objects (table_builder → worksheet_builder → liveboard_builder)
5. Import via pipeline/orchestrator.py in correct order: Tables → Worksheet → Liveboard
