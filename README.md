# CalPERS private markets performance review

How much cash have CalPERS’ private-market funds returned, and how much value is still on the books? This project uses the 31 March 2026 disclosures for 485 private equity and 66 private debt fund records. It pairs a PostgreSQL reconciliation with a three-page Power BI report.

## The report

| Page | What to look at |
| --- | --- |
| Portfolio & Vintage | Filter by programme and vintage. For 2022, median distributions per dollar paid in (DPI) were 0.24x for private debt (12 funds) and 0.02x for private equity (32 funds). The 2020 medians were closer, at 0.47x and 0.46x. |
| Manager Due Diligence | Review eight Advent and Ares funds alongside eligible peers. Advent GPE IX was at 1.49x total value to paid-in capital (TVPI) against a 1.53x median for 22 eligible 2019 funds. About 27% of its total value had been distributed. |
| Distribution Timing | Shift distributions back one year in an illustrative cash-flow model. XIRR falls from 14.99% to 12.43% and the public market equivalent falls from 1.07x to 0.94x. TVPI stays at 2.11x. |

For a browser demo, download [CalPERS-preview.html](powerbi/CalPERS-preview.html) and open it locally. To inspect the model and measures, download the repository and open [CalPERS.pbip](powerbi/CalPERS.pbip) in Power BI Desktop on Windows. Keep the Report and SemanticModel folders beside it and select **Home → Refresh**. The snapshot is embedded in the project.

## How the analysis works

[The PostgreSQL script](sql/calpers_snapshot.sql) loads the two fund tables, recalculates the multiples and matches each eligible fund to its programme and vintage peers. Vintage is the year of CalPERS’ first cash flow. In Power BI, the Programme and Vintage tables filter the fund data. DAX calculates the median across the funds selected in the report. The manager page uses fixed peer groups, with quartiles shown only where at least eight funds qualify.

All 407 comparable TVPI figures reconcile to the published one-decimal multiple within 0.05x. Another 144 records have no comparable reported multiple. Six 2020 private debt records pair a reported 0.1% IRR with a 1.2x–1.6x multiple. The original IRRs stay in the source data and are flagged for review. The public tables lack the dated transactions needed to verify them. [Validation results](docs/Validation.md)

The underlying snapshot covers one investor’s active holdings. Vintage medians describe that sample and mix several strategies. The cash-flow page uses a Takahashi–Alexander-style model and an S&P 500 total-return benchmark. Its figures are illustrative.

## Reproduce the analysis

From the repository root, with Python 3.10+ and PostgreSQL available:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/analyse.py
python src/cashflows.py
python -m unittest discover -s tests

mkdir -p powerbi/.build
psql -X -d postgres -f sql/calpers_snapshot.sql
python powerbi/build_project.py --check-sql
```

The SQL script uses temporary tables and exports results to `powerbi/.build/`. The report builder checks those results against Python before embedding the data. Run `python powerbi/build_project.py` to rebuild the report from the checked-in outputs.

| File | Contents |
| --- | --- |
| [Source table](data/source_rows.tsv) | CalPERS disclosures with programme and source-row keys |
| [Fund metrics](outputs/fund_metrics.csv) | Paid-in capital, distributions, residual value, audit flags and peer metrics |
| [Vintage summary](outputs/vintage_summary.csv) | Fund counts, medians and quartiles by programme and vintage |
| [Manager review slides](outputs/Manager_Due_Diligence.pptx) | Advent track record and due-diligence questions |
| [XIRR cross-check](outputs/Cash_Flow_XIRR_Check.xlsx) | Excel formulas for the scenario returns |

The original project also includes a five-row test of AI-assisted table extraction. The 40 extracted fields matched the source. The [prompt](workflow/extract_fund_table.md) and [matching script](src/check_pilot.py) document that test.

## Sources

- [CalPERS private equity fund performance](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance-print)
- [CalPERS private debt fund performance](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/private-debt-performance/printfunds)
- [Takahashi and Alexander, Illiquid Alternative Asset Fund Modeling](https://allocatortraining.com/wp-content/uploads/2023/06/Illiquid-Alternative-Asset-Fund-Modeling-Takahashi-Alexander.pdf)
- [Gredil, Griffiths and Stucke, The Direct Alpha Method](https://www.sciencedirect.com/science/article/pii/S0929119923000093)
- [S&P 500 annual total returns](https://www.slickcharts.com/sp500/returns)
