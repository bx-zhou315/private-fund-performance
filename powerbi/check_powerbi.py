"""Reconcile Power BI input CSVs against the existing Python audit.
Run from repository root: python powerbi/check_powerbi.py
"""
from pathlib import Path
import csv
import json
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "powerbi" / "data"
def load(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

funds = load("fact_fund.csv")
programmes = load("dim_programme.csv")
vintages = load("dim_vintage.csv")
cashflows = load("fact_cashflow.csv")
audit = json.loads((ROOT / "outputs" / "audit.json").read_text())
assert len(funds) == 551
assert len({r["fund_id"] for r in funds}) == 551
assert len(programmes) == 2
assert len(vintages) == 26
assert len(cashflows) == 23
assert Counter(r["programme_id"] for r in funds) == {"private_equity": 485, "private_debt": 66}
assert sum(r["multiple_check"] == "within rounding" for r in funds) == 407
assert sum(r["multiple_check"] == "not testable" for r in funds) == 144
assert sum(r["irr_multiple_inconsistent"] == "True" for r in funds) == 6
assert sum(r["any_quality_flag"] == "True" for r in funds) == 158
assert {r["programme_id"] for r in programmes} == {r["programme_id"] for r in funds}
assert {r["vintage"] for r in vintages} == {r["vintage"] for r in funds}

fields = {
    "paid_in_usd": "paid_in",
    "distributed_usd": "distributions",
    "total_value_usd": "distributions_plus_nav",
}
for p in ("private_equity", "private_debt"):
    subset = [r for r in funds if r["programme_id"] == p]
    for csv_field, audit_field in fields.items():
        actual = round(sum(float(r[csv_field]) for r in subset))
        expected = audit[p]["row_sums_usd"][audit_field]
        assert actual == expected, (p, csv_field, actual, expected)

sum_field = lambda col: sum(float(r[col]) for r in funds)
paid = sum_field("paid_in_usd")
distributed = sum_field("distributed_usd")
value = sum_field("total_value_usd")
nav = sum_field("remaining_value_usd")
assert round(value - distributed - nav) == 0
assert round(paid) == 159530102451
assert round(distributed) == 89549976375
assert round(value) == 235163672877
print("Fund rows:", len(funds), " | PE:", 485, " | PD:", 66)
print("Programme rows:", len(programmes), "| Vintage rows:", len(vintages))
print("TVPI matching / non-testable:", 407, "/", 144)
print("Inconsistent IRRs:", 6, "| Any quality flag:", 158)
for col in ("paid_in_usd", "distributed_usd", "remaining_value_usd", "total_value_usd"):
    print(col, f"{sum_field(col):,.0f}")
print("Pooled TVPI:", round(value / paid, 8), " | Pooled DPI:", round(distributed / paid, 8))
for scenario in sorted({r["scenario"] for r in cashflows}):
    rows = sorted((r for r in cashflows if r["scenario"] == scenario), key=lambda r: int(r["year"]))
    c = sum(float(r["contributions"]) for r in rows)
    d = sum(float(r["distributions"]) for r in rows)
    n = sum(float(r["net_cash_flow"]) for r in rows)
    assert abs(n - (d-c)) < 1e-6
    print(scenario, "years:", len(rows), "contributions:", round(c, 6),
          "distributions:", round(d, 6), "cumulative net cash flow:", round(n, 6))
print("PASS: dashboard input reconciles to project audit (not independent published totals).")
