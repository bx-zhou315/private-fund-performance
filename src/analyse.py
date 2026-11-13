"""Validate a CalPERS table snapshot and produce fund and cohort metrics."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-03-31"
BASE = "https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/"
SOURCES = {
    "private_equity": BASE + "pep-fund-performance-print",
    "private_debt": BASE + "private-debt-performance/printfunds",
}
EXPECTED = {"private_equity": 485, "private_debt": 66}
MONEY = ["commitment", "paid_in", "distributions", "distributions_plus_nav"]
SCHEMA = ["program", "source_row", "fund", "vintage", *MONEY, "irr_raw", "multiple_raw"]
KEYS = ["program", "source_row"]
FAMILY = {
    "Advent International GPE": ("Advent International", "Global Private Equity", "buyout"),
    "Ares Senior Direct Lending Fund": ("Ares Management", "Senior Direct Lending", "direct lending"),
}


def parse_reported(series, unit):
    values = series.str.replace(r"\s*\[\d+\]", "", regex=True).str.strip()
    valid = values.str.fullmatch(rf"-?\d+(?:\.\d+)?{unit}")
    invalid = ~valid & ~values.isin(["", "N/M", "N/A", "—", "-"])
    if invalid.any():
        raise ValueError(f"Unrecognised metric format: {values[invalid].tolist()}")
    return pd.to_numeric(values.where(valid).str.rstrip(unit))


def load_source():
    funds = pd.read_csv(ROOT / "data/source_rows.tsv", sep="\t", names=SCHEMA,
                        dtype=str, keep_default_na=False, quoting=3)
    funds["source_row"] = funds["source_row"].astype(int)
    funds["vintage"] = funds["vintage"].astype(int)
    counts = funds.groupby("program").size().to_dict()
    if counts != EXPECTED or funds.duplicated(KEYS).any():
        raise ValueError(f"Snapshot row count or row identity changed: {counts}")
    for program, group in funds.groupby("program"):
        if sorted(group["source_row"]) != list(range(1, EXPECTED[program] + 1)):
            raise ValueError(f"Source rows are not consecutive: {program}")
    for column in MONEY:
        raw = funds[column]
        valid = raw.str.fullmatch(r"\$-?(?:\d{1,3}(?:,\d{3})+|\d+)")
        if (~valid & ~raw.isin(["", "N/M", "N/A", "—", "-"])).any():
            raise ValueError(f"Unrecognised amount format in {column}")
        funds[column] = pd.to_numeric(raw.where(valid).str.replace(r"[$,]", "", regex=True))
    funds["source_url"] = funds["program"].map(SOURCES)
    funds["as_of"] = DATE
    funds["reported_irr_pct"] = parse_reported(funds["irr_raw"], "%")
    funds["reported_multiple"] = parse_reported(funds["multiple_raw"], "x")
    funds["early_life_flag"] = funds["vintage"].ge(
        funds["program"].map({"private_equity": 2021, "private_debt": 2020})
    ) | funds["multiple_raw"].str.contains(r"\[1\]")
    return funds


def add_metrics(funds):
    paid_in = funds["paid_in"].where(funds["paid_in"] > 0)
    funds["nav"] = funds["distributions_plus_nav"] - funds["distributions"]
    funds["dpi"] = funds["distributions"] / paid_in
    funds["rvpi"] = funds["nav"] / paid_in
    funds["tvpi"] = funds["distributions_plus_nav"] / paid_in
    funds["realised_share"] = funds["distributions"] / funds["distributions_plus_nav"].where(
        funds["distributions_plus_nav"] > 0
    )
    funds["multiple_delta"] = funds["tvpi"] - funds["reported_multiple"]
    funds["multiple_check"] = "not testable"
    comparable = funds["multiple_delta"].notna()
    funds.loc[comparable, "multiple_check"] = "within rounding"
    funds.loc[funds["multiple_delta"].abs() > 0.05000001, "multiple_check"] = "review difference"
    funds["missing_amount"] = funds[MONEY].isna().any(axis=1)
    funds["negative_amount"] = funds[MONEY + ["nav"]].lt(0).any(axis=1)
    funds["nonpositive_paid_in"] = funds["paid_in"].le(0)
    funds["paid_in_over_commitment"] = funds["paid_in"].gt(funds["commitment"])
    funds["duplicate_fund_name_vintage"] = funds.duplicated(["program", "fund", "vintage"], keep=False)
    # A near-zero IRR alongside a multiple of 1.2x or more is not plausible for a fund a few years old.
    funds["irr_multiple_inconsistent"] = funds["reported_irr_pct"].le(1) & funds["reported_multiple"].ge(1.2)
    return funds


def add_cohorts(funds):
    keys = ["program", "vintage"]
    eligible = funds.loc[
        ~funds["early_life_flag"] & ~funds["negative_amount"]
        & ~funds["duplicate_fund_name_vintage"] & funds["tvpi"].notna()
        & funds["multiple_check"].eq("within rounding")
    ].copy()
    cohorts = eligible.groupby(keys)
    eligible["eligible_cohort_n"] = cohorts["tvpi"].transform("size")
    eligible["cohort_median_tvpi"] = cohorts["tvpi"].transform("median")
    eligible["cohort_rank"] = cohorts["tvpi"].rank(ascending=False, method="average")
    eligible["sample_quartile"] = (
        4 * (eligible["cohort_rank"] - 0.5) / eligible["eligible_cohort_n"]
    ).astype(int).add(1).where(eligible["eligible_cohort_n"] >= 8)
    fields = ["eligible_cohort_n", "cohort_median_tvpi", "cohort_rank", "sample_quartile"]
    return funds.join(eligible[fields])


def run():
    funds = add_cohorts(add_metrics(load_source()))
    for prefix, (manager, family, strategy) in FAMILY.items():
        mask = funds["fund"].str.startswith(prefix)
        funds.loc[mask, ["manager", "fund_family", "strategy"]] = [manager, family, strategy]
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    funds.to_csv(out / "fund_metrics.csv", index=False, float_format="%.8f")
    funds.loc[funds["manager"].notna()].sort_values(["manager", "vintage"]).to_csv(
        out / "manager_track_records.csv", index=False, float_format="%.8f"
    )
    funds.groupby(["vintage", "program"]).agg(
        rows=("fund", "size"), dpi_n=("dpi", "count"), median_dpi=("dpi", "median"),
        tvpi_n=("tvpi", "count"), median_tvpi=("tvpi", "median"),
        p25_tvpi=("tvpi", lambda s: s.quantile(.25)),
        p75_tvpi=("tvpi", lambda s: s.quantile(.75)),
    ).reset_index().to_csv(out / "vintage_summary.csv", index=False, float_format="%.8f")
    audit = {}
    for program, group in funds.groupby("program"):
        audit[program] = {
            "rows": len(group), "multiple_check": group["multiple_check"].value_counts().to_dict(),
            "missing_amount_rows": int(group["missing_amount"].sum()),
            "missing_reported_irr_rows": int(group["reported_irr_pct"].isna().sum()),
            "nonpositive_paid_in_rows": int(group["nonpositive_paid_in"].sum()),
            "negative_amount_rows": int(group["negative_amount"].sum()),
            "duplicate_fund_name_vintage_rows": int(group["duplicate_fund_name_vintage"].sum()),
            "irr_multiple_inconsistent_rows": int(group["irr_multiple_inconsistent"].sum()),
            "early_life_rows": int(group["early_life_flag"].sum()),
            "ranked_quartile_rows": int(group["sample_quartile"].notna().sum()),
            "row_sums_usd": {name: int(group[name].sum()) for name in MONEY},
            "published_amount_total": "not supplied in source table",
        }
    (out / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    run()
