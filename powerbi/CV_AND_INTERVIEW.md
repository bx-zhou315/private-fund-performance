# CV bullet options — use only after actually building the Power BI report

**Option A (technical):**
- Built a three-page Power BI report using 551 CalPERS private fund records, with related programme and vintage tables, DAX measures and Python reconciliation checks.

**Option B (analytical):**
- Used Power BI to compare fund-level TVPI and DPI across CalPERS vintages, review data-quality flags and visualise the effect of delayed distributions in a separate illustrative cash-flow model.

**Important:** These are future-tense deliverable descriptions, **not yet earned claims**. Do not add either to your CV until you personally complete the report.

# Five interview questions and short answers

**1. Why use a star schema?**
A: Programme and vintage are reusable filter dimensions; a single fund fact table holds the numeric measures. One-to-many, single-direction relationships make report filtering predictable.

**2. Why pooled TVPI and median TVPI?**
A: Pooled TVPI = total distributed plus NAV divided by total paid-in, making larger investments count more. Median TVPI represents the typical fund and is less influenced by fund size; they answer different questions.

**3. How did you verify Power BI totals?**
A: I generated the four CSVs from the existing Python output and checked 551 unique funds, programme splits, row totals and 407 TVPI checks against the project's audit. The source tables have no independently published amount totals.

**4. Why did you leave the cash-flow table disconnected?**
A: Its cash flows are synthetic and scenario-based; the CalPERS table is a snapshot of real holdings. A relationship between model year and fund vintage would incorrectly suggest these series belong to the same investments.

**5. What would you improve with more data?**
A: I would source dated capital calls, distributions and NAV valuations, then calculate actual cash-flow-based IRRs, portfolio liquidity and properly benchmarked PME instead of assuming the model represents realised fund behaviour.
