# ts-demo-factory — CLAUDE.md

## Project purpose
Automated creation of ThoughtSpot demo environments for customers.
Input: customer name, industry, focus area.
Output: dummy data in Snowflake + TML objects (Tables, Model, Liveboard) imported into ThoughtSpot via REST API v2.

Phase 1: hardcoded retail schema. Phase 2: LLM-driven dynamic schema. Phase 3: 6-step conversational AI intake.

---

## Architecture overview

```
config/settings.py               ← all env vars, loaded once via Settings.from_env()
ts_client/auth.py                ← ThoughtSpotAuth: Bearer token with caching + auto re-auth
ts_client/tml_api.py             ← TMLClient: import_tml(), export_tml(), delete_by_name()
schema/retail/tables.py          ← TableDef + ColumnDef dataclasses (4 tables) — retail fallback
schema/retail/data_gen.py        ← Faker generators driven by ColumnDef
tml_builder/table_builder.py     ← TableDef → thoughtspot_tml.Table → YAML
tml_builder/model_builder.py     ← Jinja2 template → thoughtspot_tml.Model → YAML
tml_builder/liveboard_builder.py ← Jinja2 template → thoughtspot_tml.Liveboard → YAML
snowflake_client/loader.py       ← DDL from TableDef, bulk INSERT (RSA key pair auth)
pipeline/orchestrator.py         ← runs steps in order, threads GUIDs between steps
scripts/step1_ts_api_test.py     ← smoke test (Gate 1)
scripts/run_demo.py              ← simple CLI intake + LLM schema + pipeline
scripts/run_intake.py            ← AI-guided entry point (6-step conversational intake + pipeline)
scripts/run_intake_only.py       ← runs only the AI intake phase, no Snowflake/TS
scripts/intake_simple.py         ← original simple CLI questionnaire (used by run_demo.py)
scripts/generate_schema.py       ← calls Claude API → JSON star schema
scripts/schema_to_pipeline.py    ← JSON schema → TableDef list + join specs
intake/intake_ai.py              ← IntakeEngine: 6-step conversational state machine
intake/intake_prompts.py         ← SYSTEM_PROMPTS + EXTRACTION_PROMPTS dicts
intake/skills/star_schema.md     ← injected into schema step system prompt
intake/skills/ts_visualizations.md ← comprehensive viz reference, injected into liveboard step
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
# fill in .env — including ANTHROPIC_API_KEY

# Step 1 smoke test
python -m scripts.step1_ts_api_test

# Test schema generation only (no pipeline)
python -m scripts.generate_schema

# Test JSON → TableDef translation only (no pipeline)
python -m scripts.schema_to_pipeline

# Test AI intake only (no Snowflake, no TS)
python -m scripts.run_intake_only
python -m scripts.run_intake_only --save   # saves intake_output.json

# Full pipeline — simple CLI intake + LLM schema
python -m scripts.run_demo
python -m scripts.run_demo --skip-snowflake

# Full pipeline — AI-guided 6-step conversational intake
python -m scripts.run_intake
python -m scripts.run_intake --skip-snowflake
python -m scripts.run_intake --row-count 50000   # overrides intake volume selection
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for schema generation |
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

## Status (updated 2026-03-10)

### Phase 1 — COMPLETE ✓
Full pipeline works end-to-end (retail schema, hardcoded):
1. Creates 4 Snowflake tables + loads 10K rows each (40K total)
2. Imports Table TMLs → gets table GUIDs
3. Cleans up old Model + Liveboard by name
4. Imports Model TML → gets model GUID
5. Imports Liveboard TML → renders charts correctly

### Phase 2 — COMPLETE ✓
LLM-driven schema generation + dynamic pipeline fully wired and tested (Pet Center demo):

| Component | File | Status |
|-----------|------|--------|
| CLI intake questionnaire | `scripts/intake_simple.py` | ✓ done |
| Claude API schema gen | `scripts/generate_schema.py` | ✓ done |
| JSON → TableDef translation | `scripts/schema_to_pipeline.py` | ✓ done |
| `run_demo.py` uses intake + LLM | `scripts/run_demo.py` | ✓ done |
| Pipeline accepts dynamic tables | `pipeline/orchestrator.py` | ✓ done |
| Dynamic Model TML template | `templates/dynamic/model.tml.j2` | ✓ done |
| Dynamic Liveboard TML template | `templates/dynamic/liveboard.tml.j2` | ✓ done |
| Schema cache + --skip-snowflake | `scripts/run_demo.py` | ✓ done |

### Phase 3 — COMPLETE ✓
Conversational AI intake (6-step flow) replacing the simple CLI questionnaire:

| Component | File | Status |
|-----------|------|--------|
| IntakeEngine state machine | `intake/intake_ai.py` | ✓ done |
| Step prompts + extraction | `intake/intake_prompts.py` | ✓ done |
| Star schema skill | `intake/skills/star_schema.md` | ✓ done |
| Liveboard skill | `intake/skills/ts_liveboard.md` | ✓ done |
| AI entry point | `scripts/run_intake.py` | ✓ done |
| Intake-only test script | `scripts/run_intake_only.py` | ✓ done |
| Dataset config step (5/6) | `intake/intake_prompts.py` + `intake_ai.py` | ✓ done |
| years + patterns in data_gen | `schema/retail/data_gen.py` | ✓ done |
| years + patterns in orchestrator | `pipeline/orchestrator.py` | ✓ done |

#### AI intake: 6-step flow
```
1. Customer context  — company name + web search (CZ/SK priority, then global)
2. Analytics domain  — 4–6 domain options based on company context
3. Use-case          — 3 concrete use-case proposals
4. Schema design     — ASCII star schema, iterative confirmation
5. Dataset config    — volume (10K/100K/1M), years history, patterns (seasonality, anomalies…)
6. Liveboard design  — 3–5 chart proposals with resolved column names
```

#### Data patterns (implemented in data_gen.py)
- `seasonality` — ×1.6 multiplier on measures for March–August rows
- `anomalies`   — 2% of rows get ×5 measure spike
- `regional_variance`, `promo_events`, `own_brand_growth` — stored/passed, not yet injected

#### Sentinel phrases (step confirmation detection)
```
context:   "Let's move on"
domain:    "Domain confirmed"
usecase:   "Moving to schema design"
schema:    "Schema confirmed"
dataset:   "Dataset configured"
liveboard: "Building your demo"
```

### Open items
1. **Spotter/Sage enable** — no REST API endpoint; must be done manually in TS UI:
   - Data → Model → select model → More options → Enable Sage
2. **New Snowflake table registration** — still manual (connection/update API broken):
   - After each run, register `{CUSTOMER}_*` tables in TS UI
   - Data → Add data → Browse connection → select tables
3. **Pattern injection** — `regional_variance`, `promo_events`, `own_brand_growth` not yet implemented in data_gen

### Environment (dev)
- TS instance: `https://techpartners.thoughtspot.cloud`
- SF account: `jxgpfar-revolt_partner` | DB: `_REVOLT_ANALYTICS_DEV` | Schema: `RADO`
- TS connection ID: `76372876-5a62-4016-b4fa-84499feb6be5` (Revolt Snowflake Playground)
- TS connection SF role: `_R_DEVELOPER` | warehouse: `HACKATHON_WH`
- `venv/` exists and is fully installed
- Anthropic API key: in `.env` as `ANTHROPIC_API_KEY`

### Claude API notes
- Model used: `claude-sonnet-4-6`
- `output_config` JSON schema NOT supported on this model — use system prompt approach
- Claude returns relationships in inconsistent formats across calls (3 formats seen):
  `fact_table/fact_column`, `from_table/from_column`, `from/on` — all handled in `json_to_joins()`
- `max_tokens=4096` needed to avoid truncation of larger schemas

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
- Dynamic pipeline creates customer-prefixed tables: `PET_CENTER_INVENTORY_FACT` etc. — register those, not the bare names

### BOOLEAN data type not supported in TS Table TML
- TS rejects `data_type: BOOLEAN` on import with: `Data type BOOLEAN is not valid for column...`
- **Fix:** `schema_to_pipeline.py` maps `BOOLEAN` → `VARCHAR` (stores `'true'`/`'false'` strings)
- `_faker_for()` checks `IS_` / `HAS_` prefixes and returns `random_element(["true", "false"])`

### Customer-prefixed table names (dynamic pipeline)
- Dynamic pipeline prefixes all table names with `{SAFE_CUSTOMER_NAME}_` to avoid clashes between demos
- e.g. Pet Center → `PET_CENTER_INVENTORY_FACT`, `PET_CENTER_PRODUCT_DIM` etc.
- Implemented in `orchestrator.py` with `dataclasses.replace()` on TableDef + joins remapping
- After Snowflake load, register the prefixed names in TS UI

### Spotter/Sage enable — must be done manually in TS UI
- No REST API v2 endpoint exists for enabling Spotter on a model
- TML approach (`is_sage_enabled: true`) confirmed ignored by TS — inject removed from `model_builder.py`
- **Manual steps:** Data → Model → select model → More options → Enable Sage

### --skip-snowflake flag + schema_cache.json
- Full run saves `schema_cache.json` with both `schema` and `config`
- `--skip-snowflake` loads from cache (no intake questionnaire, no Snowflake)
- Use after: (a) tables already loaded in Snowflake, (b) manually registered in TS UI
- Cache file: `ts-demo-factory/schema_cache.json` (gitignored)
