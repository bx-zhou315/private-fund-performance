# Validation notes

The report uses the saved 31 March 2026 CalPERS snapshot. Source-row checks reconcile saved table text and derived records. The cash-flow checks use the original project’s illustrative quarterly series.

| Check | Result |
| --- | ---: |
| Source records with distinct programme and source-row keys | 551 |
| Private equity / private debt records | 485 / 66 |
| Recalculated TVPI within 0.05x of the reported multiple | 407 of 407 |
| Maximum absolute difference | 0.049975x |
| Records without a comparable reported multiple | 144 |
| Zero paid-in record whose ratios stay blank | 1 |
| Debt IRRs flagged for review | 6, all in the 2020 vintage |
| Descriptive programme–vintage cohorts | 33 |
| Records with an eligible sample quartile | 145 |
| Base / delayed cash-flow observations, with the opening zero row | 41 / 45 |

The six flagged IRRs are each reported as 0.1% alongside a 1.2x–1.6x reported multiple. The review flag preserves the published value and excludes it from the usable IRR count. Fund-level cash-flow dates would be needed to establish what explains the combination.

| Illustrative metric | Base case | Distributions one year later |
| --- | ---: | ---: |
| XIRR | 14.99% | 12.43% |
| TVPI | 2.11x | 2.11x |
| KS-PME | 1.07x | 0.94x |
| Direct Alpha | 1.26% | −0.99% |
| Funding trough per 100 committed | −71.84 | −78.11 |
| Terminal NAV | 0.00 | 0.00 |

The independent check solves XIRR via Newton iteration and uses annual benchmark returns to reproduce quarter-end index levels. It compares every net cash flow, cumulative cash flow and benchmark level, and confirms that the delay shifts all distributions by four quarters. The delayed path has no interim NAV estimate.

For Desktop acceptance, open the PBIP, refresh the seven Import tables, run the three DAX checks and exercise the Programme, Vintage and Manager slicers. Expected DAX query outputs are the portfolio counts above, 0.24x for 12 private debt observations and 0.02x for 32 private equity observations in 2022, and a −2.56 percentage-point XIRR change. The report definition files pass Microsoft’s published JSON schemas. Opening, refreshing and rendering in Power BI Desktop require Windows.
