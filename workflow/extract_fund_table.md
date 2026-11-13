# Prompt: extract a fund performance table

I use this prompt to turn a fund performance disclosure (web table or PDF) into a CSV that Python can check. Before running it, tell the model which programme, report date and rows to extract.

## Prompt

> Extract the fund performance table from this disclosure into CSV, in the same row order as the source, with this header:
>
> `program,source_row,fund,vintage,commitment,paid_in,distributions,distributions_plus_nav,irr_raw,multiple_raw`
>
> Rules:
> - One row per fund or vehicle. Keep the full fund name, including suffixes such as "-B" or "Co-Invest".
> - `source_row` is the row number in the source table, starting at 1 below the header. Skip headers, notes and total rows.
> - Copy numbers exactly as shown, for example "$1,234,000". Keep zeros, negative signs, "N/M" and footnote markers, written as "13.3% [1]".
> - If a cell is blank or unreadable, leave it blank. Never fill a value from another column or another row.
> - "Cash Out" is distributions. "Cash Out & Remaining Value" already includes distributions, so do not label it NAV.
> - Do not convert units unless the source states the scale.
> - After the CSV, list the source URL, as-of date, table or page, row range and any published totals.
> - If you cannot see some of the requested rows, say which ones instead of guessing.

## Checks before using the output

The model can copy a number wrongly without saying so, so every extraction goes through these checks in Python (`src/analyse.py` and `src/check_pilot.py`):

1. Row count, row order and duplicate names match the source.
2. No missing amounts, no zero paid-in capital, no unexpected negative values.
3. TVPI recalculated from the amounts matches the reported multiple, within half of the last displayed digit (0.05x for one-decimal multiples).
4. Reported IRR and multiple are consistent with each other.
5. Field totals match published totals where the source gives them.
6. On a test sample, every field is compared with the source. Check 3 alone would miss a wrongly copied distribution if the combined total was copied correctly.

The first test ran this prompt with ChatGPT on five rows across the CalPERS private equity and private debt tables. All 40 fields matched (`workflow/ai_pilot.csv`, `outputs/ai_pilot_check.json`).
