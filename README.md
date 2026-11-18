# Private Fund Performance Analysis

A first-pass LP review of CalPERS private equity and private debt holdings, using the public fund performance tables as at 31 March 2026. The project covers data extraction and checking, fund-level metrics, a manager track-record case study (Advent International GPE) and a cash-flow model showing how distribution timing affects IRR and PME. The PostgreSQL pipeline and three-page Power BI report turn the analysis into a reproducible portfolio review.

## Explore the report

| Page | What to look at |
| --- | --- |
| Portfolio & Vintage | Filter by programme or vintage and compare median DPI and TVPI. The quality table shows reported-multiple reconciliation and usable IRR coverage. |
| Manager Due Diligence | Compare the cash and residual components of eight Advent and Ares case funds. The peer table shows cohort size, median TVPI and quartile where eligible. |
| Distribution Timing | Compare two illustrative scenarios to see how delaying distributions affects cash needs, XIRR and public-market-relative results. |

Open the whole [Power BI Project folder](powerbi) in a recent Power BI Desktop on Windows by opening [CalPERS.pbip](powerbi/CalPERS.pbip), then select **Home → Refresh**. The report, semantic model and snapshot travel together. Keep both sibling folders next to the entry file. The embedded Power Query Import partitions require no credentials or database connection. Desktop can save a PBIX copy once the refresh finishes.

For a browser walkthrough, download [CalPERS-preview.html](powerbi/CalPERS-preview.html) and open it locally. The standalone preview includes all three views. See [validation results](docs/Validation.md) and the [Chinese walkthrough](docs/Quickstart_ZH.md).

## Key findings

- **Advent GPE track record.** GPE VIII-B (2016) ranked in the top quartile of the 2016 CalPERS sample (8 funds). GPE IX (2019) is at 1.49x TVPI against a 1.53x median for 22 comparable 2019 funds, close to the median, but only about 27% of its value has been distributed. The rest is NAV, so the key diligence question is how and when that NAV turns into cash.
- **GPE X (2022)** is at 1.29x TVPI with 0.02x DPI. CalPERS marks it as early-life, so it is too early to judge.
- **Private debt vs private equity.** In the 2022 vintage, private debt funds had returned more cash than private equity (median DPI 0.24x vs 0.02x), consistent with credit paying income earlier. In 2020 the two were similar (0.47x vs 0.46x). These are single-date snapshots, not proof of a persistent difference.
- **Distribution timing.** In the cash-flow model, delaying all distributions by one year cuts XIRR from 15.0% to 12.4% and KS-PME from 1.07x to 0.94x, while TVPI stays at 2.11x.
- **Data issue.** CalPERS shows a 0.1% net IRR for six 2020-vintage private debt funds whose multiples are 1.2x to 1.6x. These values warrant review. The report preserves the published IRRs and excludes the six observations from usable IRR coverage. A dated transaction history would be needed to verify them.

## How to run

Python 3.10 or newer, from this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/analyse.py
python src/check_pilot.py
python src/cashflows.py
python -m unittest discover -s tests
```

From the repository root with a running PostgreSQL instance, run the SQL reconciliation and rebuild the report:

```bash
mkdir -p powerbi/.build
psql -X -d postgres -f sql/calpers_snapshot.sql
python3 powerbi/build_project.py --check-sql
```

Use the standard PostgreSQL connection environment variables or add your connection arguments to `psql`. The script loads the raw snapshot into session-scoped objects, exports fund metrics and cohort summaries, and leaves no permanent database tables. The builder compares the exports with the original Python outputs before embedding the fund values. To rebuild directly from the checked-in analysis outputs, run `python3 powerbi/build_project.py`.

| Path | Contents |
|---|---|
| `sql/calpers_snapshot.sql` | PostgreSQL staging, joins, audit flags, cohort aggregates and ranking |
| `powerbi/CalPERS.pbip` | Entry file for the three-page Power BI project |
| `powerbi/checks.dax` | Three validation queries for Power BI Desktop |
| `data/source_rows.tsv` | Source table values with programme and row position |
| `data/sp500_annual_total_returns.csv` | S&P 500 calendar-year total returns, 2015–2025 |
| `workflow/extract_fund_table.md` | Reusable AI extraction prompt with checking rules |
| `workflow/ai_pilot.csv` | Five rows extracted with ChatGPT using the prompt |
| `outputs/audit.json` | Row counts, missing values, multiple checks and flags |
| `outputs/fund_metrics.csv` | Metrics, quality flags and vintage comparisons for every fund |
| `outputs/manager_track_records.csv` | Six Advent GPE funds and two Ares Senior Direct Lending funds |
| `outputs/vintage_summary.csv` | Medians and quartiles by programme and vintage |
| `outputs/Manager_Due_Diligence.pptx` | Four-slide Advent review |
| `outputs/Cash_Flow_XIRR_Check.xlsx` | Excel XIRR formulas checking the Python results |

## Data checks

- Row counts and row order are checked against the source: 485 private equity and 66 private debt funds.
- TVPI is recalculated from paid-in capital, distributions and remaining value. All 407 funds with a reported multiple agree within 0.05x, since CalPERS shows multiples to one decimal place. The other 144 funds have no comparable multiple (mostly N/M) and are kept but not ranked.
- Other flags: missing or negative amounts, zero paid-in capital (one fund), duplicate names and implausible IRR and multiple combinations.
- The tables publish no amount totals, so field totals cannot be reconciled.
- **AI extraction test.** The prompt in `workflow/extract_fund_table.md` was run with ChatGPT on five rows across the two tables, and all 40 fields matched the source. A formula check alone would miss a mis-copied distribution if the combined total were right, so the test compares every field.

## Model and comparison rules

The model has one fund-snapshot fact table, a small eight-row manager case table, a scenario table and a quarterly cash-flow fact table. The Programme and Vintage dimensions filter both fund tables, Manager filters the case table, and Scenario filters Cash Flow. DAX calculates medians within the selected context. SQL computes the pre-defined eligible cohort ranks.

The portfolio chart medians include all computable ratios for each programme and vintage. Manager peer statistics use the narrower set of eligible funds. The two numbers can differ for the same vintage.

## Definitions

- DPI = Cash Out / Cash In. Residual NAV = (Cash Out & Remaining Value) − Cash Out. RVPI = NAV / Cash In. TVPI = DPI + RVPI.
- Cash In includes contributions for investments and fees.
- Vintage is the year of CalPERS' first cash flow, which can differ from the fund's own vintage.
- Quartiles compare funds in the same programme and vintage, excluding early-life and non-reconciling funds, and are shown only where at least eight funds qualify.

## Limitations

- The data covers one LP's active holdings. Exited funds are excluded, and the vehicles include co-investments and managed accounts.
- Strategies are mixed within each vintage, so the quartiles describe this sample, not the industry.
- Cumulative figures cannot reproduce the reported IRRs or give an actual PME. That needs dated cash flows.
- The cash-flow model is illustrative: Takahashi–Alexander style, 10-year life, 15% annual NAV growth, bow of 2.5. The benchmark is the S&P 500 total return, interpolated between year-ends. A real comparison should match the fund's geography, currency and strategy.

## Sources

- [CalPERS Private Equity Program Fund Performance Review](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance-print)
- [CalPERS Private Debt Program Fund Performance Review](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/private-debt-performance/printfunds)
- [Takahashi and Alexander, Illiquid Alternative Asset Fund Modeling](https://allocatortraining.com/wp-content/uploads/2023/06/Illiquid-Alternative-Asset-Fund-Modeling-Takahashi-Alexander.pdf)
- [Gredil, Griffiths and Stucke, Benchmarking Private Equity: The Direct Alpha Method](https://www.sciencedirect.com/science/article/pii/S0929119923000093)
- [S&P 500 annual total returns](https://www.slickcharts.com/sp500/returns)
- [Microsoft Excel XIRR documentation](https://support.microsoft.com/en-us/excel/functions/xirr-function)
- [Microsoft Power BI Projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
