"""Reconcile the source snapshot and independently check the illustrative model."""
import csv
import json
import math
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "powerbi" / ".build"
OUTPUTS = ROOT / "outputs"
PROGRAMMES = {"private_equity": "Private Equity", "private_debt": "Private Debt"}
SCENARIOS = {"base": "Base case", "delayed": "Distributions +1 year"}
D = Decimal


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def number(text):
    return float(text) if text else None


def source_amount(raw):
    return int(raw.removeprefix("$").replace(",", ""))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, message, tolerance=1e-8):
    require(
        (actual is None and expected is None)
        or (actual is not None and expected is not None and abs(actual - expected) <= tolerance),
        f"{message}: got {actual}, expected {expected}",
    )


def check_funds():
    with (ROOT / "data" / "source_rows.tsv").open(encoding="utf-8", newline="") as stream:
        raw = list(csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    funds = read_csv(OUTPUTS / "fund_metrics.csv")
    source = {(row[0], row[1]): row[2:] for row in raw}
    require(len(funds) == len(source) == len(raw) == 551, "Source and output row counts")
    require({(f["program"], f["source_row"]) for f in funds} == set(source), "Fund identity")
    require([sum(f["program"] == p for f in funds) for p in PROGRAMMES] == [485, 66], "Programme counts")

    deltas = []
    for fund in funds:
        key = fund["program"], fund["source_row"]
        name, vintage, committed, paid, cash, total, irr, multiple = source[key]
        require((name, vintage, irr, multiple) == tuple(
            fund[f] for f in ("fund", "vintage", "irr_raw", "multiple_raw")
        ), f"Source descriptors {key}")
        amounts = list(map(source_amount, (committed, paid, cash, total)))
        require(amounts == [int(fund[f]) for f in (
            "commitment", "paid_in", "distributions", "distributions_plus_nav"
        )], f"Source amounts {key}")
        _, paid, cash, total = amounts
        nav = total - cash
        require(int(fund["nav"]) == nav, f"NAV {key}")
        for col, value in (("dpi", cash), ("rvpi", nav), ("tvpi", total)):
            close(number(fund[col]), float(D(value) / D(paid)) if paid > 0 else None, f"{col} {key}")
        close(number(fund["realised_share"]), cash / total if total > 0 else None, f"Realised share {key}")
        reported = multiple.split()[0].removesuffix("x")
        if reported != "N/M" and paid > 0:
            delta = abs(D(total) / D(paid) - D(reported))
            require(delta <= D("0.05"), f"Reported multiple {key}")
            deltas.append(delta)

    flags = [f for f in funds if f["irr_multiple_inconsistent"] == "True"]
    require(len(deltas) == 407 and len(flags) == 6, "Comparable multiples and IRR flags")
    require(all(f["program"] == "private_debt" and f["vintage"] == "2020"
                and f["reported_irr_pct"] == "0.10000000" for f in flags), "2020 debt IRR flags")
    require(sum(not f["tvpi"] for f in funds) == 1, "Zero-denominator count")
    keys = {(f["program"], f["vintage"]) for f in funds}
    cohorts = read_csv(OUTPUTS / "vintage_summary.csv")
    require({(r["program"], r["vintage"]) for r in cohorts} == keys and len(cohorts) == len(keys),
            "Cohort identities")
    for row in cohorts:
        key = row["program"], row["vintage"]
        group = [f for f in funds if (f["program"], f["vintage"]) == key]
        require(len(group) == int(row["rows"]), f"Cohort size {key}")
        for col in ("dpi", "tvpi"):
            values = [float(f[col]) for f in group if f[col]]
            require(len(values) == int(row[f"{col}_n"]), f"{col} observations {key}")
            close(number(row[f"median_{col}"]), median(values) if values else None, f"Median {col} {key}")
    return funds, cohorts, float(max(deltas))


def compare_sql(funds, cohorts):
    """Verify each PostgreSQL row against the independent Python pipeline."""
    sql = {(r["program"], r["source_row"]): r for r in read_csv(BUILD / "fund_snapshot.csv")}
    require(set(sql) == {(f["program"], f["source_row"]) for f in funds}, "SQL fund keys")
    numbers = {
        "total_value": "distributions_plus_nav", "peer_count": "eligible_cohort_n",
        "peer_median_tvpi": "cohort_median_tvpi", "quartile": "sample_quartile",
        **{col: col for col in (
            "commitment", "paid_in", "distributions", "nav", "dpi", "rvpi", "tvpi",
            "realised_share", "reported_multiple", "reported_irr_pct", "cohort_rank", "multiple_delta"
        )},
    }
    flags = {
        "early_life": "early_life_flag", "irr_flag": "irr_multiple_inconsistent",
        "duplicate_fund": "duplicate_fund_name_vintage",
        **{col: col for col in ("missing_amount", "negative_amount", "nonpositive_paid_in", "paid_in_over_commitment")},
    }
    for fund in funds:
        key = fund["program"], fund["source_row"]
        row = sql[key]
        for col in ("vintage", "fund", "manager"):
            require(row[col] == fund[col], f"SQL {col} {key}")
        for col, reference in numbers.items():
            close(number(row[col]), number(fund[reference]), f"SQL {col} {key}")
        for col, reference in flags.items():
            require((row[col] == "t") == (fund[reference] == "True"), f"SQL {col} {key}")
        status = {"within rounding": "Within rounding", "not testable": "No comparable multiple",
                  "review difference": "Review difference"}
        require(row["multiple_check"] == status[fund["multiple_check"]], f"SQL multiple check {key}")
    sql_cohorts = read_csv(BUILD / "cohort_summary.csv")
    require(len(sql_cohorts) == len(cohorts), "SQL cohort count")
    for actual, expected in zip(sql_cohorts, cohorts):
        require(all(actual[c] == expected[c] for c in ("program", "vintage")), "SQL cohort key")
        for col in set(expected) - {"program", "vintage"}:
            close(number(actual[col]), number(expected[col]), f"SQL cohort {col}")
    # The report uses PostgreSQL's derived values when SQL has been run.
    for fund in funds:
        row = sql[fund["program"], fund["source_row"]]
        for col, reference in numbers.items():
            fund[reference] = row[col]
        for col, reference in flags.items():
            fund[reference] = str(row[col] == "t")
    return sql_cohorts


def calculate_rate(dates, cash):
    years = [(day - dates[0]).days / 365 for day in dates]
    rate = 0.10
    for _ in range(30):
        value = sum(flow * (1 + rate) ** -t for t, flow in zip(years, cash))
        if abs(value) < 1e-11:
            return rate
        slope = sum(-t * flow * (1 + rate) ** (-t - 1) for t, flow in zip(years, cash))
        rate -= value / slope
    raise ValueError("Illustrative XIRR Newton check did not converge")


def check_cashflows():
    expected = json.loads((OUTPUTS / "model_results.json").read_text())
    annual_returns = {
        int(r["year"]): float(r["total_return_pct"]) / 100
        for r in read_csv(ROOT / "data" / "sp500_annual_total_returns.csv")
    }
    data, results = {}, {}
    for key in SCENARIOS:
        rows = read_csv(OUTPUTS / f"model_{key}.csv")
        dates = [date.fromisoformat(r["date"]) for r in rows]
        require(len(rows) == {"base": 41, "delayed": 45}[key], f"{key} quarter count")
        require(dates[0] == date(2014, 12, 31) and all(
            d.year * 4 + d.month // 3 == 2014 * 4 + 4 + i and d.month in (3, 6, 9, 12)
            and d.day == (30 if d.month in (6, 9) else 31) for i, d in enumerate(dates)
        ), f"{key} quarter-end dates")
        calls = [float(r["call"]) for r in rows]
        distributions = [float(r["distribution"]) for r in rows]
        terminal_nav = float(rows[-1]["nav"])
        net = [distribution - call for call, distribution in zip(calls, distributions)]
        running = [sum(net[:i + 1]) for i in range(len(net))]
        levels = [100.0] + [
            100 * math.prod(1 + annual_returns[y] for y in range(2015, day.year))
            * (1 + annual_returns[day.year]) ** (day.month / 12)
            for day in dates[1:]
        ]
        for row, flow, total, level in zip(rows, net, running, levels):
            close(float(row["net_cashflow"]), flow, f"{key} net flow")
            close(float(row["cumulative_net_cashflow"]), total, f"{key} cumulative flow")
            close(float(row["benchmark_level"]), level, f"{key} public benchmark")
        factors = [levels[-1] / level for level in levels]
        net[-1] += terminal_nav
        metrics = {
            "xirr": calculate_rate(dates, net),
            "tvpi": (sum(distributions) + terminal_nav) / sum(calls),
            "ks_pme": (sum(x * f for x, f in zip(distributions, factors)) + terminal_nav)
                      / sum(x * f for x, f in zip(calls, factors)),
            "direct_alpha": calculate_rate(dates, [x * f for x, f in zip(net, factors)]),
            "terminal_nav": terminal_nav,
            "trough": min(running),
        }
        require(terminal_nav == 0, f"{key} terminal NAV")
        for metric, value in metrics.items():
            close(value, expected[key][metric], f"{key} {metric}")
        results[key] = expected[key]
        data[key] = rows
    require([r["call"] for r in data["delayed"]] == [r["call"] for r in data["base"]] + ["0.000000000"] * 4,
            "Calls are unchanged")
    require([r["distribution"] for r in data["delayed"]] == ["0.000000000"] * 4
            + [r["distribution"] for r in data["base"]], "All distributions shift four quarters")
    require(all(not r["nav"] for r in data["delayed"][:-1]), "Delayed interim NAV unavailable")
    return data, results
