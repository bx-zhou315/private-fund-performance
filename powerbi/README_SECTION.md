## Power BI portfolio extension (web browser / Mac)

This optional extension uses **Power BI Service** to report on the **551 CalPERS private equity/private debt holdings (snapshot 31 March 2026)** and to visualise a **separate illustrative distribution-timing sensitivity**. The supplied input tables are generated from the repository's existing Python outputs; the reporting layer is assembled manually in Power BI to demonstrate model building, DAX, filtering, visuals and reconciliation.

### Files and model

- `powerbi/data/fact_fund.csv` — one row per fund (551), financial amounts and quality-review fields.
- `powerbi/data/dim_programme.csv` — programme slicer dimension (2 rows).
- `powerbi/data/dim_vintage.csv` — vintage slicer dimension (26 rows).
- `powerbi/data/fact_cashflow.csv` — annual model cash flows by scenario (23 rows), unrelated to underlying CalPERS fund cash flows.
- `powerbi/check_powerbi.py` — verify figures against the original `outputs/audit.json`.
- `powerbi/BUILD_GUIDE.md` — the full user-operated web reporting steps and measures.

`dim_programme` and `dim_vintage` each have single-direction one-to-many relationships to `fact_fund`. `fact_cashflow` stays disconnected to prevent synthetic model values from being confused with portfolio holdings.

### Measures and validation

Main measures: Fund Count, Total Paid-in, Total Distributed, Pooled TVPI, Pooled DPI, Median TVPI by vintage, % of funds flagged, and Cumulative Net Cash Flow. The DAX definitions and formatting guidance are in `BUILD_GUIDE.md`.

Run `python powerbi/check_powerbi.py`; compare report totals and counts to the printed output. Expected: 551 fund rows (485 equity, 66 debt), 407 reported multiple checks within rounding and 144 not testable. Six inconsistent reported IRRs are flagged. The script reconciles to **Python row totals**; the original CalPERS source tables do not publish amount totals.

### Limitations

- Fund data describe a single LP's holdings at a single date and exclude exited vehicles; mixed strategies, managed accounts and co-investments affect comparability.
- Vintage is defined by CalPERS' first cash flow, not necessarily fund inception.
- Fund-level TVPI and DPI are not time series; fund-level realised cash-flow timing and actual portfolio IRRs cannot be inferred from this snapshot.
- The calculated median across all visible funds is **not** the quality-screened peer quartile calculation in `outputs/vintage_summary.csv`.
- Early-life funds and missing multiples should not be described as erroneous. The 'any quality flag' review indicator includes potentially legitimate paid-in-over-commitment situations.
- The Takahashi–Alexander-style cash-flow scenario is **illustrative**, with arbitrary model units and an initial commitment of 100, not actual CalPERS cash flow. The comparison isolates distribution timing and must not be presented as observed fund performance.
- Web report export, publishing and downloading options depend on workspace entitlements and file upload route.

**Build status:** Data prepared and checked. Screenshots, a live report link and any claimed Power BI hands-on experience should be added **only after the dashboard has actually been built**.
