# Power BI Service: one-day hands-on build guide (Mac)

**Use Power BI Service in your Mac browser** at https://app.powerbi.com/; no Windows virtual machine is needed for this scoped report. This is **not a Power BI Desktop guide**. The web model editor supports Power Query, relationships and DAX measures, subject to account/workspace/source limitations. See Microsoft's *Edit semantic models in the Power BI service* documentation: https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models

## 0. Ground rules (read before building)

- The fund table is a **CalPERS holdings snapshot as at 31 March 2026**. Neither yearly fund performance nor dated underlying fund cash flows are supplied.
- `fact_cashflow.csv` is a **separate, illustrative model**. Its amounts are model units based on an initial commitment of 100, **not USD and not CalPERS funds**. Never sum it with the fund figures.
- `net_irr_pct` is reported percentage points, e.g. 10.1 means 10.1%, not a decimal fraction. Do not calculate its mean as a portfolio IRR.
- TVPI = (distributed + remaining value) / paid-in; DPI = distributed / paid-in; RVPI = remaining value / paid-in.
- A **pooled multiple** weights implicitly by capital invested, while a **median multiple** describes the middle fund. Both are useful, but do not treat them as equal.
- `any_quality_flag` includes paid-in-over-commitment (which can be economically legitimate) and an inconsistent reported IRR; the flag is **review required**, not necessarily a confirmed error. `early_life_flag` is a separate lifecycle indicator and is not automatically counted as an error.

## 1. Import the files (25–35 min)

1. Open https://app.powerbi.com/ and sign in. Use **My workspace**.
2. Start the service's current **New item / Get data / Create semantic model** path, depending on your UI. Prefer the **Excel workbook upload** route if your account does not offer a multi-file CSV import into one model: on your Mac, create a workbook with **four named Excel Tables** (`fact_fund`, `dim_programme`, `dim_vintage`, `fact_cashflow`), each populated from the provided CSV. Upload that workbook to the service as a semantic model. This is a transport wrapper only; the supplied source data remains the four CSVs.
3. If your workspace supports **Power Query online / Add data**, you may instead import the four files within the same semantic model there. **Do not** create four independent semantic models by uploading each CSV separately: relationships cannot be created between disconnected models in the simple workflow.
4. In Power Query check column types:
   - `fact_fund`: `vintage` Whole number; `*_usd`, `tvpi`, `dpi`, `rvpi`, `net_irr_pct`, `reported_multiple`, `multiple_delta` Decimal number; all `*_flag` and named Boolean fields True/False (Logical). Keep `fund_id`, `fund`, `programme_id`, `programme`, `multiple_check` as Text.
   - `dim_vintage[vintage]` Whole number and `dim_programme[programme_id]` Text.
   - `fact_cashflow[year]` Whole number; contributions, distributions, net_cash_flow Decimal; scenario Text.
5. Blank reported IRR / multiple / multiple_delta means missing; **leave as null**, never replace with 0. Verify `fund_id` contains 551 unique values. If Boolean flags are imported as text, convert them via Power Query before using the DAX below.
6. Save/apply the query, then open the semantic model in **Editing mode**.

## 2. Relationships (10 min)

Create two **one-to-many, single-direction** relationships:

`dim_programme[programme_id]` (1) -> `fact_fund[programme_id]` (*)

`dim_vintage[vintage]` (1) -> `fact_fund[vintage]` (*)

These dimensions provide clean slicers and filter the 551-row fact table. `fact_cashflow` remains **disconnected by design**: its year/scenario describe a synthetic illustration and cannot be joined meaningfully to CalPERS fund vintage or programme. Do **not** connect `fact_cashflow[year]` to `dim_vintage[vintage]`.

## 3. DAX measures (20 min)

In model Editing mode, choose a table and **New measure**, paste one formula per measure. For base monetary measures format as US dollars, Display units = Billions; for multiples format number to two decimals and use a title containing 'x'. For measures on `fact_cashflow`, use model units, **not $**.

```dax
Fund Count = DISTINCTCOUNT(fact_fund[fund_id])
```
Counts unique fund records within current filters.

```dax
Total Paid-in = SUM(fact_fund[paid_in_usd])
```
Sums cash invested in the selected funds (USD).

```dax
Total Distributed = SUM(fact_fund[distributed_usd])
```
Sums returned cash in the selected funds (USD).

```dax
Total Remaining Value = SUM(fact_fund[remaining_value_usd])
```
Sums reported residual NAV in the selected funds (USD).

```dax
Pooled TVPI = DIVIDE(SUM(fact_fund[total_value_usd]), [Total Paid-in])
```
Capital-weighted aggregate TVPI; not the mean of fund TVPIs.

```dax
Pooled DPI = DIVIDE([Total Distributed], [Total Paid-in])
```
Capital-weighted cash distributions relative to paid-in.

```dax
Median TVPI by vintage = MEDIAN(fact_fund[tvpi])
```
Median across selected, nonblank fund TVPIs; with vintage on the axis, it returns a median per vintage. **This raw dashboard median is not the project's quality-filtered vintage ranking median**: if you need a like-for-like comparison to `vintage_summary.csv`, reproduce its eligibility rules in a separate measure.

```dax
Flagged Funds = CALCULATE([Fund Count], fact_fund[any_quality_flag] = TRUE())
```
Counts funds flagged for review.

```dax
% of funds flagged = DIVIDE([Flagged Funds], [Fund Count])
```
Fraction of selected funds with at least one review flag; format as percentage.

```dax
TVPI Checked Funds = CALCULATE([Fund Count], fact_fund[multiple_check] = "within rounding")
```
Counts funds whose reported multiple agrees with the calculated TVPI to the permitted rounding.

```dax
TVPI Not Testable = CALCULATE([Fund Count], fact_fund[multiple_check] = "not testable")
```
Counts funds without a comparable reported multiple; these must not be labelled validation failures.

```dax
Contributions (model units) = SUM(fact_cashflow[contributions])
```
Yearly contribution total for the selected synthetic scenario.

```dax
Distributions (model units) = SUM(fact_cashflow[distributions])
```
Yearly distribution total for the selected synthetic scenario.

```dax
Cumulative Net Cash Flow =
VAR SelectedYear = MAX(fact_cashflow[year])
RETURN
CALCULATE(
    SUM(fact_cashflow[net_cash_flow]),
    FILTER(
        ALL(fact_cashflow[year]),
        fact_cashflow[year] <= SelectedYear
    )
)
```
Running sum of net cash flow over years; keeps scenario filter context, so Base and Delayed remain separate series. Only use in a yearly-axis visual.

> If the service imports flags as TEXT instead of TRUE/FALSE, fix the Power Query type rather than editing the measures to compare text.

## 4. Report pages (45–75 min)

**Page 1 — Overview: CalPERS fund-level portfolio snapshot**
- Cards: `Fund Count`, `Total Paid-in`, `Total Distributed`, `Pooled TVPI`, `Pooled DPI`.
- Line chart: X `dim_vintage[vintage]`; Y `Median TVPI by vintage` and optionally a separate DPI median measure. **Do not** place a pooled DPI series beside median TVPI and label both 'typical fund'.
- Slicers: `dim_programme[programme]`, `dim_vintage[vintage]`.
- Callout: this is a cross-sectional vintage comparison, **not** a time series of evolving performance. Vintage age differs.
- Visual validation: select Private Equity, expect 485; select Private Debt, expect 66.

**Page 2 — Data quality: what's reliable to compare?**
- Cards: `TVPI Checked Funds` = 407, `TVPI Not Testable` = 144, `Flagged Funds`, `% of funds flagged`.
- Bar chart for flags: the easiest one-day approach is create six **individual count measures** using `CALCULATE([Fund Count], fact_fund[flag_name] = TRUE())`, then use six cards; a proper flag-type bar chart would require a separate unpivoted flag table and additional modelling. Keep it simple if under time pressure.
- Table: fund, programme, vintage, paid-in, distributed, TVPI, reported_multiple, multiple_delta, multiple_check, nonpositive_paid_in, paid_in_over_commitment, irr_multiple_inconsistent. Visual filter `any_quality_flag = True`.
- Check IRR anomalies: filter `irr_multiple_inconsistent = True`; expect **6**, all private debt vintage 2020.
- The 407 are *within rounding*, not an exact reproduction of the printed one-decimal multiple.

**Page 3 — Cash-flow timing: why cash timing matters**
- Use only `fact_cashflow`.
- Clustered columns: X = year, Y = `Contributions (model units)` and `Distributions (model units)`; slicer scenario, or small multiples.
- Line chart: X = year, Y = `Cumulative Net Cash Flow`, Legend = scenario. This distinguishes Base vs one-year delayed distributions.
- Caption: *Illustrative Takahashi–Alexander-style model; figures are model units for a commitment of 100, not actual CalPERS fund cash flows*.
- Explain model results from `outputs/model_results.json`: XIRR 15.0% -> 12.4%; KS-PME 1.07x -> 0.94x; TVPI approximately 2.11x for both. These are **Python model results, not DAX-computed IRRs**.

## 5. Reconcile and present (15 min)

In Terminal at repo root:
```bash
python powerbi/check_powerbi.py
```
Compare **unfiltered** report cards with printed counts and totals. Check scenarios separately. Note source tables have no published amount totals, so this verifies agreement between dashboard inputs and project Python audit, **not independent audited CalPERS total figures**.

Use consistent navy/teal/orange tones, readable axis labels and ≤ 5 headline KPIs per page. Titles should state what the chart measures; only make a claim about a finding once supported by actual filtered data. Prefer a clear 3-page report over visual clutter.

## 6. Save / portfolio proof

Save report in My workspace. Capture screenshots of each page, Model view (two relationships), 2–3 DAX measures, and the reconciliation output. Link the GitHub repo. Avoid promising a `.pbix` file: Microsoft documents restrictions on downloading reports whose underlying model came from uploaded local CSV/Excel. Confirm export options in your own tenant before advertising this as a downloadable Desktop file.

If workspace or account restrictions block adding all four tables to **one semantic model**, do not pretend the build works: a single four-table Excel workbook upload is the first fallback; a Windows Desktop build is the later fallback. A report built from separate independent uploaded CSV semantic models is not the same star-schema demonstration.
