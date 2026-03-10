# ThoughtSpot Liveboard Design Rules

## Column name resolution (CRITICAL — gets the TML right)
ThoughtSpot resolves column names when it processes the model. Use RESOLVED names in TML fields:

| Column name (schema) | Model display name | Resolved name in TML |
|---|---|---|
| `REVENUE` (MEASURE, SUM) | Revenue | **Total Revenue** |
| `QUANTITY` (MEASURE, SUM) | Quantity | **Total Quantity** |
| `DISCOUNT_RATE` (MEASURE, AVG) | Discount Rate | **Average Discount Rate** |
| `REGION` (ATTRIBUTE) | Region | **Region** |
| `PRODUCT_CATEGORY` (ATTRIBUTE) | Product Category | **Product Category** |

**Resolution rules:**
- Display name = column name → replace `_` with space → title-case (e.g. `PRODUCT_CATEGORY` → `Product Category`)
- Attribute `attr_resolved` = display name (unchanged)
- Measure `measure_resolved`:
  - "Total {display_name}" — default for SUM aggregation (most measures)
  - "Average {display_name}" — for columns containing: DISCOUNT, RATE, RATIO, PCT, PERCENT, MARGIN

## search_query syntax
```
SUM measure:     [Revenue] [Region]
AVERAGE measure: average [Discount Rate] [Category]
```
- Always wrap column names in `[brackets]`
- Use display names (with spaces), not resolved names, not UPPER_SNAKE_CASE
- `average` keyword triggers AVERAGE aggregation

## Chart type selection
| Type | Best for | Example |
|---|---|---|
| **KPI** | Single headline metric for the most important measures; typically compared to a target or prior period (e.g. vs last year, vs budget) | Total Overstock Value vs. Last Year |
| **BAR** | Ranking categories horizontally | Revenue by Region |
| **COLUMN** | Time-based categories (month/quarter on X) | Revenue by Quarter |
| **LINE** | Continuous trends over time | Monthly Revenue Trend |
| **PIE** | Part-to-whole composition | Revenue Share by Category |
| **SCATTER** | Correlation between two measures | Revenue vs Quantity by Product |

**Guidelines:**
- Always include a LINE chart if there's a DATE column — shows trends (great for demos)
- BAR charts show rankings well — best for regional or product comparisons
- PIE: max 5–6 slices; avoid for more than 6 categories
- 3–5 charts is ideal — enough to tell a story without overwhelming

## Required TML fields (omitting either causes "Index 0 out of bounds" error)
Every chart visualization MUST include:
- `chart_columns` — list of column IDs used in the chart
- `axis_configs` — x and y axis mapping

## Layout
- 2 charts per row (width: 6 each, x: 0 and 6)
- Height: 4 units per row
- Lead with the most impactful business question
