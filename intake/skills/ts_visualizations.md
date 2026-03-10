# ThoughtSpot Liveboard Visualization Reference

> Authoritative reference for building liveboard TML. Every YAML snippet has been verified
> by import → export round-trip against a live ThoughtSpot instance.

---

## 1. Visualization Object Hierarchy

```
liveboard:
  visualizations:              # list of PinnedVisualization
    - id: viz_1                # referenced by layout.tiles
      answer:                  # AnswerEDocProto
        name: ...
        tables: [{id, name, fqn}]
        search_query: "..."
        answer_columns: [{name}]
        table: ...             # TableVisualization (always present)
        chart: ...             # ChartVisualization (always present)
        display_mode: ...      # "CHART_MODE" or "TABLE_MODE"
      display_headline_column: ...  # only for KPI headlines (viz level, NOT inside answer)
  layout:
    tiles:
      - visualization_id: viz_1
        x: 0
        y: 0
        height: 4
        width: 6
```

---

## 2. Column Name Resolution (CRITICAL)

ThoughtSpot resolves column names at import time. Use **resolved names** in all TML fields
except `search_query` (which uses display names).

### Rules
1. **Display name** = column name with `_` → space, title-cased
   - `PRODUCT_CATEGORY` → `Product Category`
   - `REVENUE` → `Revenue`

2. **Resolved name** (used in `answer_columns`, `table_columns`, `chart_columns`, `axis_configs`):
   - ATTRIBUTE: same as display name → `Product Category`
   - MEASURE with SUM: `Total {display_name}` → `Total Revenue`
   - MEASURE with AVERAGE: `Average {display_name}` → `Average Discount Rate`

3. **When to use AVERAGE**: column name contains any of:
   `DISCOUNT`, `RATE`, `RATIO`, `PCT`, `PERCENT`, `MARGIN`

### Resolved name patterns

| Aggregation | Column example | Display name | Resolved name |
|-------------|---------------|--------------|---------------|
| SUM (default) | `REVENUE` | Revenue | **Total Revenue** |
| AVERAGE | `DISCOUNT_RATE` | Discount Rate | **Average Discount Rate** |
| COUNT | `count [Order Id]` | Order Id | **Count of Order Id** |
| COUNT_DISTINCT | `unique count [Region]` | Region | **Unique Count of Region** |
| MIN | `min [Revenue]` | Revenue | **Min Revenue** |
| MAX | `max [Revenue]` | Revenue | **Max Revenue** |
| DATE `.daily` | `[Date] daily` | Date | **Day(Date)** |
| DATE `.weekly` | `[Date] weekly` | Date | **Week(Date)** |
| DATE `.monthly` | `[Date] monthly` | Date | **Month(Date)** |
| DATE `.quarterly` | `[Date] quarterly` | Date | **Quarter(Date)** |
| DATE `.yearly` | `[Date] yearly` | Date | **Year(Date)** |
| DATE `day of week` | `[Date] day of week` | Date | **Day of Week(Date)** |

### search_query syntax
- Uses **display names** (NOT resolved names) wrapped in `[brackets]`
- SUM measure: `[Revenue] [Region]`
- AVERAGE measure: `average [Discount Rate] [Category]`
- KPI (single measure): `[Revenue]`
- Time-based: `[Revenue] [Date] monthly`
- The `average` keyword triggers AVERAGE aggregation

### search_query keywords

| Category | Keyword | Example | Effect |
|----------|---------|---------|--------|
| Aggregation | `average` | `average [Discount Rate]` | AVERAGE agg |
| Aggregation | `unique count` | `unique count [Customer Id]` | COUNT_DISTINCT |
| Aggregation | `count` | `count [Order Id]` | COUNT |
| Aggregation | `min` / `max` | `min [Revenue]` | MIN / MAX |
| Aggregation | `sum` | `sum [Revenue]` | Explicit SUM |
| Date bucket | `monthly` | `[Date] monthly` | Group by month |
| Date bucket | `quarterly` | `[Date] quarterly` | Group by quarter |
| Date bucket | `yearly` | `[Date] yearly` | Group by year |
| Date bucket | `weekly` | `[Date] weekly` | Group by week |
| Date bucket | `daily` | `[Date] daily` | Group by day |
| Date bucket | `day of week` | `[Date] day of week` | Day of Week(Date) |
| Ranking | `top` / `bottom` | `top 10 [Product] [Revenue]` | Limit results |
| Sorting | `sort by` | `[Region] [Revenue] sort by [Revenue] descending` | Explicit sort |
| Date filter | `last n years/months` | `[Revenue] last 2 years` | Rolling window |
| Date filter | `last year` / `this month` | `[Revenue] last year` | Period shortcut |
| Date filter | `after` / `before` | `[Date] after 01/01/2024` | Date boundary |
| Date filter | `between...and` | `[Date] between 01/01/2024 and 12/31/2024` | Date range |
| Growth | `growth of` | `growth of [Revenue] by [Date] monthly` | Period-over-period % |
| Period-to-date | `year to date` | `[Revenue] year to date` | YTD aggregate |

---

## 3. Chart Types

### Valid `chart.type` values
`BAR`, `COLUMN`, `LINE`, `PIE`, `AREA`, `SCATTER`, `BUBBLE`,
`STACKED_COLUMN`, `STACKED_BAR`, `STACKED_AREA`,
`WATERFALL`, `TREEMAP`, `HEATMAP`, `FUNNEL`, `PARETO`, `SANKEY`,
`LINE_COLUMN`, `LINE_STACKED_COLUMN`, `SPIDER_WEB`,
`PIVOT_TABLE`, `GRID_TABLE`,
`GEO_AREA`, `GEO_BUBBLE`, `GEO_HEATMAP`,
`GEO_EARTH_BAR`, `GEO_EARTH_AREA`, `GEO_EARTH_GRAPH`,
`GEO_EARTH_BUBBLE`, `GEO_EARTH_HEATMAP`,
`DONUT`, `CANDLESTICK`, `WHISKER_SCATTER`

> **KPI is NOT a chart type.** It is a TABLE_MODE visualization with headline. See section 4.

### Recommended types for demos
| Type | Best for | X axis | Y axis |
|------|----------|--------|--------|
| BAR | Ranking categories horizontally | Attribute | Measure |
| COLUMN | Time-based categories (month/quarter) | Time attribute | Measure |
| LINE | Continuous trends over time | Date | Measure |
| PIE | Part-to-whole (max 5-6 slices) | Attribute | Measure |
| STACKED_BAR | Category breakdown with sub-groups | Attribute | Measure (+color) |
| SCATTER | Correlation between two measures | Measure 1 | Measure 2 |
| DONUT | Alternative to PIE | Attribute | Measure |
| AREA | Trend with volume emphasis | Date | Measure |

---

## 4. Visualization Templates

### 4a. Standard Chart (BAR, COLUMN, LINE, PIE, etc.)

```yaml
- id: viz_1
  answer:
    name: Revenue by Region          # human-readable title
    tables:
      - id: My_Model
        name: My_Model
        fqn: <model_guid>
    search_query: "[Revenue] [Region]"
    answer_columns:
      - name: Region                 # attr resolved name
      - name: Total Revenue          # measure resolved name
    table:
      table_columns:
        - column_id: Region
          headline_aggregation: COUNT_DISTINCT
        - column_id: Total Revenue
          headline_aggregation: SUM
      ordered_column_ids:
        - Region
        - Total Revenue
      client_state: ""
    chart:
      type: BAR                      # any valid chart type
      chart_columns:
        - column_id: Region
        - column_id: Total Revenue
      axis_configs:
        - x:
            - Region
          y:
            - Total Revenue
      client_state: ""
    display_mode: CHART_MODE
```

**Required fields** (omitting causes "Index 0 out of bounds" error):
- `chart.chart_columns` — list of column IDs
- `chart.axis_configs` — x and y mapping
- `answer_columns` — resolved column names
- `table.table_columns` — with `column_id` and `headline_aggregation`
- `table.ordered_column_ids`
- `chart.client_state: ""` and `table.client_state: ""`

### 4b. KPI Headline

KPI is **not** a chart type. It uses `display_mode: TABLE_MODE` with `display_headline_column`
at the visualization level (sibling of `answer`, NOT inside it).

```yaml
- id: viz_1
  answer:
    name: Total Revenue
    tables:
      - id: My_Model
        name: My_Model
        fqn: <model_guid>
    search_query: "[Revenue]"        # single measure, no attribute
    answer_columns:
      - name: Total Revenue          # only the measure
    table:
      table_columns:
        - column_id: Total Revenue
          show_headline: true
          headline_aggregation: SUM
      ordered_column_ids:
        - Total Revenue
      client_state: ""
    chart:
      type: COLUMN                   # dummy — not rendered
      chart_columns:
        - column_id: Total Revenue
      axis_configs:
        - x: []                      # empty x axis
          y:
            - Total Revenue
      client_state: ""
    display_mode: TABLE_MODE         # NOT CHART_MODE
  display_headline_column: Total Revenue   # ← viz level, outside answer
```

**Key differences from standard chart:**
- `display_mode: TABLE_MODE` (not `CHART_MODE`)
- `display_headline_column` at visualization level (sibling of `answer`)
- `show_headline: true` on table_columns (optional but recommended)
- `answer_columns` has only the measure (no attribute)
- `search_query` has only the measure
- `axis_configs.x` is empty `[]`
- `chart.type` can be anything (ignored, not rendered)

### 4c. LINE chart with Date

```yaml
- id: viz_1
  answer:
    name: Revenue Trend
    tables:
      - id: My_Model
        name: My_Model
        fqn: <model_guid>
    search_query: "[Revenue] [Date] monthly"
    answer_columns:
      - name: Month(Date)            # TS resolves [Date] monthly → Month(Date)
      - name: Total Revenue
    table:
      table_columns:
        - column_id: Month(Date)
          headline_aggregation: COUNT_DISTINCT
        - column_id: Total Revenue
          headline_aggregation: SUM
      ordered_column_ids:
        - Month(Date)
        - Total Revenue
      client_state: ""
    chart:
      type: LINE
      chart_columns:
        - column_id: Month(Date)
        - column_id: Total Revenue
      axis_configs:
        - x:
            - Month(Date)
          y:
            - Total Revenue
      client_state: ""
    display_mode: CHART_MODE
```

**Date resolution patterns:**
- `[Date] daily` → resolved name: `Day(Date)`
- `[Date] weekly` → resolved name: `Week(Date)`
- `[Date] monthly` → resolved name: `Month(Date)`
- `[Date] quarterly` → resolved name: `Quarter(Date)`
- `[Date] yearly` → resolved name: `Year(Date)`
- `[Date] day of week` → resolved name: `Day of Week(Date)`

---

## 5. axis_configs Structure

```yaml
axis_configs:
  - x:                   # list of attribute/time columns
      - Region
    y:                   # list of measure columns
      - Total Revenue
    color:               # (optional) list — color/legend grouping
      - Category
    size:                # (optional) string — bubble size
    hidden:              # (optional) list — hidden columns
    category:            # (optional) list — category columns
```

- For KPI: `x: []` (empty list)
- For SCATTER: both x and y can be measures
- For STACKED: use `color` for the stacking dimension

---

## 6. headline_aggregation Values

Used in `table.table_columns[].headline_aggregation`:

| Value | Use for |
|-------|---------|
| `SUM` | Measure columns (revenue, quantity, cost) |
| `AVERAGE` | Rate/ratio measures |
| `COUNT` | Row count |
| `COUNT_DISTINCT` | Attribute columns (count unique values) |
| `MIN` | Minimum value |
| `MAX` | Maximum value |
| `TABLE_AGGR` | Table-level aggregation |

---

## 7. Layout Grid

```yaml
layout:
  tiles:
    - visualization_id: viz_1
      x: 0              # horizontal position (0-based)
      y: 0              # vertical position (0-based)
      height: 4         # tile height in grid units
      width: 6          # tile width in grid units
```

### Standard layout patterns

**KPI row** (top of dashboard):
- 3 KPIs across: each `width: 4, height: 2, y: 0`, x: `0, 4, 8`
- 2 KPIs across: each `width: 6, height: 2, y: 0`, x: `0, 6`

**Chart grid** (below KPIs):
- 2 per row: each `width: 6, height: 4`, x: `0` and `6`
- Full width: `width: 12, height: 4`
- Grid is 12 units wide

**Recommended dashboard layout:**
```
Row 0 (y=0):  [KPI w=4] [KPI w=4] [KPI w=4]     height=2
Row 1 (y=2):  [Chart w=6      ] [Chart w=6      ] height=4
Row 2 (y=6):  [Chart w=6      ] [Chart w=6      ] height=4
Row 3 (y=10): [Chart w=12 (full width)           ] height=4
```

---

## 8. display_mode Values

| Value | Renders as | Use case |
|-------|-----------|----------|
| `CHART_MODE` | Chart visualization | BAR, LINE, PIE, etc. |
| `TABLE_MODE` | Table or KPI headline | KPI headlines, data tables |

---

## 9. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Index 0 out of bounds for length 0` | Missing `chart_columns` or `axis_configs` | Add both with correct resolved column names |
| `Invalid AnswerColumns [None]` | `answer_columns` has a None/missing name | Ensure resolved names are correct, not None |
| `Data type BOOLEAN is not valid` | BOOLEAN in table TML | Map BOOLEAN → VARCHAR |
| Liveboard GUID = None | Import silently failed | Check `response.status.error_message` |
| Charts show "Error in loading data" | Column names don't match model | Verify resolved names match model column names exactly |

---

## 10. Checklist Before Import

1. ✅ All column names in TML use **resolved names** (not display names, not UPPER_SNAKE)
2. ✅ `search_query` uses **display names** in `[brackets]`
3. ✅ Every chart has `chart_columns` + `axis_configs` + `client_state: ""`
4. ✅ Every table has `table_columns` + `ordered_column_ids` + `client_state: ""`
5. ✅ KPI charts use `TABLE_MODE` + `display_headline_column` at viz level
6. ✅ `answer_columns` match resolved names exactly
7. ✅ Layout tiles reference correct `visualization_id` values
8. ✅ Model `fqn` GUID is valid and model exists in TS
