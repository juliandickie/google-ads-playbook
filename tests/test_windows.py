import unittest
from pathlib import Path
from gads_playbook import windows, io

WS = Path(__file__).parent / "fixtures" / "ws60"

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
    def test_verdicts(self):
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        by = {c["campaign"]: c for c in r["campaigns"]}
        self.assertEqual(by["Search | NonBrand | BOF | Winner"]["verdict"], "scale")
        self.assertTrue(by["Search | NonBrand | BOF | Winner"]["budget_limited"])
        noisy = by["Search | NonBrand | BOF | Noisy"]
        self.assertEqual(noisy["verdict"], "hold")
        self.assertGreater(noisy["windows"][7]["cur"]["roas"], 4.0)
        self.assertLess(noisy["windows"][30]["cur"]["roas"], 4.0)
        self.assertTrue(any("30" in s for s in noisy["reasons"]))
        self.assertEqual(by["Search | NonBrand | TOF | Loser"]["verdict"], "cut")
    def test_window_arithmetic(self):
        r = windows.compute(self.c, target_roas=4.0)
        w = {c["campaign"]: c for c in r["campaigns"]}["Search | NonBrand | BOF | Winner"]["windows"][7]
        self.assertEqual(w["cur"]["cost"], 700_000_000)
        self.assertAlmostEqual(w["cur"]["conversions"], 35.0)
        self.assertAlmostEqual(w["cur"]["cpa"], 20.0)
        self.assertEqual(r["end_date"], "2026-08-31")
        self.assertEqual(r["unavailable"], [])
    def test_short_history_marks_unavailable(self):
        short = [x for x in self.c if x["segments.date"] >= "2026-08-12"]  # 20 days
        r = windows.compute(short, target_roas=4.0)
        self.assertEqual(r["unavailable"], [14, 30])
        self.assertIn(7, r["campaigns"][0]["windows"])
    def test_render(self):
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        md = windows.render_md(r, "AUD")
        self.assertIn("scale", md)
        self.assertIn("7 days", md)

if __name__ == "__main__":
    unittest.main()
