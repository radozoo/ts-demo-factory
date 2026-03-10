# Star Schema Design Rules for ThoughtSpot

## Data types
- **INT64** — integer IDs, counts, whole-number quantities
- **VARCHAR** — text: names, categories, codes, statuses. Also use for boolean flags (store 'true'/'false' as strings)
- **DOUBLE** — decimal measures: revenue, cost, price, rate, margin, discount
- **DATE** — date fields. Do NOT use TIMESTAMP — ThoughtSpot handles DATE better
- **BOOLEAN is NOT supported** in ThoughtSpot Table TML — always substitute VARCHAR

## Structure
- One **fact table**: 5–12 columns (PK + FK per dimension + DATE + 2–5 measures)
- **2–4 dimension tables**: 4–8 columns each (PK + descriptive attributes, no measures)
- Grain of fact table: one row = one business event (sale, order, visit, transaction)
- Every dimension needs exactly one PK column
- Fact table has one FK per dimension, named identically to the dimension's PK

## Naming conventions
- UPPER_SNAKE_CASE everywhere, no exceptions
- Fact table: `{SUBJECT}_FACT` (e.g. `SALES_FACT`, `ORDERS_FACT`)
- Dimensions: `{ENTITY}_DIM` (e.g. `PRODUCT_DIM`, `CUSTOMER_DIM`, `STORE_DIM`)
- PKs: `{ENTITY}_ID` — must match FK name in fact exactly (e.g. `PRODUCT_ID` in both tables)

## Column type rules
- **ATTRIBUTE**: IDs, foreign keys, names, categories, statuses, date columns — anything you GROUP BY or FILTER on
- **MEASURE**: additive numeric values — revenue, quantity, cost, price — anything you SUM, COUNT, or AVERAGE

## Avoid
- Duplicate column names across tables (ThoughtSpot shows "(2)" suffix on duplicates — confusing in demos)
- More than 4 dimension tables (model becomes unwieldy)
- DATE column in a dimension — always put time dimension in the fact table
- Measures in dimension tables (move them to the fact table)
- Snowflaked dimensions (no dimension pointing to another dimension)

## Industry patterns
- **Retail/e-commerce**: SALES_FACT → PRODUCT_DIM, STORE_DIM (or CHANNEL_DIM), CUSTOMER_DIM, DATE in fact
- **SaaS/subscription**: REVENUE_FACT → CUSTOMER_DIM, PRODUCT_DIM, CONTRACT_DIM
- **Healthcare**: VISIT_FACT → PATIENT_DIM, PROVIDER_DIM, FACILITY_DIM, DIAGNOSIS_DIM
- **Logistics/supply chain**: SHIPMENT_FACT → ORIGIN_DIM, DESTINATION_DIM, CARRIER_DIM, PRODUCT_DIM
- **Finance**: TRANSACTION_FACT → ACCOUNT_DIM, MERCHANT_DIM, CATEGORY_DIM
