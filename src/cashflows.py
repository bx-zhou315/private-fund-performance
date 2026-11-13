"""Illustrative quarterly Takahashi–Alexander-style model and dated returns."""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Assumptions:
    commitment: float = 100.0
    life_years: int = 10
    annual_growth: float = .15
    bow: float = 2.5


def model(a):
    dates = pd.date_range("2014-12-31", periods=a.life_years * 4 + 1, freq="QE")
    rows = [{"date": dates[0].date(), "call": 0., "distribution": 0., "nav": 0.}]
    unfunded, nav = a.commitment, 0.
    for quarter, timestamp in enumerate(dates[1:], start=1):
        # Apply the draw rate to uncalled capital and the payout rate to grown opening NAV.
        annual_call_rate = .42 if quarter <= 8 else .27 if quarter <= 16 else 0.
        call = unfunded * (1 - (1 - annual_call_rate) ** .25)
        unfunded -= call
        grown_nav = nav * (1 + a.annual_growth) ** .25
        annual_payout_rate = (quarter / (4 * a.life_years)) ** a.bow
        payout_rate = 1 - (1 - annual_payout_rate) ** .25
        distribution = grown_nav * payout_rate
        nav = grown_nav + call - distribution
        rows.append({"date": timestamp.date(), "call": call, "distribution": distribution, "nav": nav})
    return pd.DataFrame(rows)


def xirr(dates, amounts):
    """Bisection for conventional flows within the stated rate bracket."""
    dates, amounts = list(dates), list(amounts)
    nonzero = [value for value in amounts if value]
    if not nonzero or nonzero[0] >= 0 or nonzero[-1] <= 0:
        raise ValueError("Expected an initial outflow and a later inflow")
    years = [(day - dates[0]).days / 365 for day in dates]

    def xnpv(rate):
        return sum(value / (1 + rate) ** year for year, value in zip(years, amounts))

    lower, upper = -.90, 5.
    if xnpv(lower) <= 0 or xnpv(upper) >= 0:
        raise ValueError("XIRR root is outside the model's bracket")
    for _ in range(100):
        rate = (lower + upper) / 2
        if xnpv(rate) > 0:
            lower = rate
        else:
            upper = rate
    return (lower + upper) / 2


def delay_distributions(base):
    # All distributions move four quarters. Contributions and nominal proceeds are unchanged.
    dates = pd.date_range(base.date.iloc[0], periods=len(base) + 4, freq="QE").date
    delayed = pd.DataFrame({"date": dates})
    delayed["call"] = base["call"].reindex(delayed.index, fill_value=0.)
    delayed["distribution"] = base["distribution"].reindex(delayed.index, fill_value=0.).shift(
        4, fill_value=0.
    )
    # Only terminal NAV is needed for return metrics. No interim NAV is assumed for this sensitivity.
    delayed["nav"] = float("nan")
    delayed.loc[delayed.index[-1], "nav"] = 0.
    return delayed


def benchmark_levels(dates):
    """Chain published annual total returns and interpolate geometric quarterly levels."""
    annual = pd.read_csv(ROOT / "data/sp500_annual_total_returns.csv").set_index("year")
    year_end = 100 * (1 + annual["total_return_pct"] / 100).cumprod()
    year_end.loc[annual.index.min() - 1] = 100.
    levels = [100.]
    for day in dates.iloc[1:]:
        opening, closing = year_end.loc[day.year - 1], year_end.loc[day.year]
        levels.append(opening * (closing / opening) ** (day.month / 12))
    return levels


def assess(rows):
    rows["net_cashflow"] = rows["distribution"] - rows["call"]
    rows["cumulative_net_cashflow"] = rows["net_cashflow"].cumsum()
    rows["benchmark_level"] = benchmark_levels(rows["date"])
    factor = rows["benchmark_level"].iloc[-1] / rows["benchmark_level"]
    terminal_nav = rows["nav"].iloc[-1]
    terminal_cashflow = rows["net_cashflow"].copy()
    terminal_cashflow.iloc[-1] += terminal_nav
    index_scaled = terminal_cashflow * factor
    return {
        "xirr": xirr(rows["date"], terminal_cashflow),
        "tvpi": (rows["distribution"].sum() + terminal_nav) / rows["call"].sum(),
        "ks_pme": ((rows["distribution"] * factor).sum() + terminal_nav)
        / (rows["call"] * factor).sum(),
        "direct_alpha": xirr(rows["date"], index_scaled),
        "terminal_nav": terminal_nav,
        "trough": rows["cumulative_net_cashflow"].min(),
    }


def run():
    import json

    a = Assumptions()
    base = model(a)
    delayed = delay_distributions(base)
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    stats = {"base": assess(base), "delayed": assess(delayed)}
    assert abs(stats["base"]["tvpi"] - stats["delayed"]["tvpi"]) < 1e-12
    assert stats["delayed"]["xirr"] < stats["base"]["xirr"]
    assert abs(stats["base"]["terminal_nav"]) < 1e-10
    for name, rows in (("base", base), ("delayed", delayed)):
        rows.to_csv(out / f"model_{name}.csv", index=False, float_format="%.9f")
    (out / "model_results.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    run()
