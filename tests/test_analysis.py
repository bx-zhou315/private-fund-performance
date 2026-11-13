"""Regression checks for source conventions and return calculations."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analyse import add_cohorts, add_metrics, load_source
from cashflows import Assumptions, assess, delay_distributions, model, xirr


class FundAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.funds = add_cohorts(add_metrics(load_source()))

    def test_paid_in_and_combined_value(self):
        fund = self.funds.loc[self.funds["fund"].eq("Advent International GPE IX Limited Partnership")].iloc[0]
        self.assertEqual(fund.nav, 578_768_864)
        self.assertAlmostEqual(fund.dpi + fund.rvpi, fund.tvpi)
        self.assertAlmostEqual(fund.tvpi, 1.4873587)
        self.assertEqual(fund.sample_quartile, 3)

    def test_source_footnotes_and_rounding(self):
        self.assertEqual(self.funds["multiple_check"].eq("within rounding").sum(), 407)
        self.assertEqual(self.funds["multiple_check"].eq("not testable").sum(), 144)
        credit = self.funds[self.funds["program"].eq("private_debt")]
        self.assertTrue(credit["early_life_flag"].all())
        self.assertTrue(credit["sample_quartile"].isna().all())
        self.assertEqual(self.funds["tvpi"].isna().sum(), 1)

    def test_dated_returns(self):
        self.assertAlmostEqual(xirr([date(2021, 1, 1), date(2022, 1, 1)], [-100, 110]), .10)

    def test_distribution_delay(self):
        a = Assumptions()
        base = model(a)
        delayed = delay_distributions(base)
        self.assertAlmostEqual(base["distribution"].sum(), delayed["distribution"].sum())
        for original, shifted in zip(base["distribution"], delayed["distribution"].iloc[4:]):
            self.assertAlmostEqual(original, shifted)
        baseline, sensitivity = assess(base), assess(delayed)
        self.assertAlmostEqual(baseline["tvpi"], sensitivity["tvpi"])
        self.assertLess(sensitivity["xirr"], baseline["xirr"])


if __name__ == "__main__":
    unittest.main()
