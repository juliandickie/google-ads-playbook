import unittest
from pathlib import Path
from gads_playbook import misallocate, io

WS = Path(__file__).parent / "fixtures" / "ws"

class MisallocateTests(unittest.TestCase):
    def setUp(self):
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
    def test_winner_and_loser_detection(self):
        r = misallocate.compute(self.t, self.c)
        winners = {w["term"] for w in r["winners"]}
        losers = {l["term"] for l in r["losers"]}
        # magnesium bisglycinate 400mg: 15 conv / 60 clicks = 25% CVR, cost 29 of the campaign's 2829 term cost = 1.0% share
        self.assertIn("magnesium bisglycinate 400mg", winners)
        # cheap magnesium tablets: 6 conv / 800 clicks = 0.75% CVR, cost 1100 of 2829 = 38.9% share
        self.assertIn("cheap magnesium tablets", losers)
        # best sleep supplement: 7/400 = 1.75% CVR, 500/2829 = 17.7% share -> loser
        self.assertIn("best sleep supplement", losers)
        # magnesium powder has 1 conversion, under the minimum, so it appears nowhere
        self.assertNotIn("magnesium powder", winners | losers)
    def test_share_uses_campaign_term_cost(self):
        r = misallocate.compute(self.t, self.c)
        w = next(x for x in r["winners"] if x["term"] == "magnesium bisglycinate 400mg")
        self.assertAlmostEqual(w["share"], 29 / 2829, places=4)
        self.assertAlmostEqual(w["cvr"], 0.25)
    def test_thresholds_are_parameters(self):
        r = misallocate.compute(self.t, self.c, min_conversions=1, win_cvr=0.02, win_share=0.5)
        self.assertIn("magnesium powder", {w["term"] for w in r["winners"]})
    def test_reallocation_and_render(self):
        r = misallocate.compute(self.t, self.c)
        self.assertTrue(any("dedicated" in x["proposal"] for x in r["reallocation"]))
        md = misallocate.render_md(r, "AUD")
        self.assertIn("Underfunded winners", md)
        self.assertIn("Overfunded losers", md)

if __name__ == "__main__":
    unittest.main()
