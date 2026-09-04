import json
import unittest
from pathlib import Path
from gads_playbook import misallocate, io

WS = Path(__file__).parent / "fixtures" / "ws"
WINDOWS = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-03-04"}
MATCHING_WINDOWS = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-06-03"}

class MisallocateTests(unittest.TestCase):
    def setUp(self):
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
    def test_winner_and_loser_detection(self):
        # windows differ (the fixture's own gads.json), so the share denominator is term cost.
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
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
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
        w = next(x for x in r["winners"] if x["term"] == "magnesium bisglycinate 400mg")
        self.assertAlmostEqual(w["share"], 29 / 2829, places=4)
        self.assertAlmostEqual(w["cvr"], 0.25)
        self.assertEqual(r["share_basis"], "term_cost")
    def test_share_uses_reported_campaign_cost_when_windows_match(self):
        # R31: with matching (or unknown) windows the denominator is the campaign's reported cost from
        # campaigns.csv (1208.2), not the term cost (2829). At the default 0.02 share threshold the term's
        # 2.4% share is no longer a winner, so widen win_share to recover the row and check the value directly.
        r = misallocate.compute(self.t, self.c, windows=MATCHING_WINDOWS)
        self.assertEqual(r["share_basis"], "campaign_cost")
        self.assertNotIn("magnesium bisglycinate 400mg", {w["term"] for w in r["winners"]})
        r_wide = misallocate.compute(self.t, self.c, windows=MATCHING_WINDOWS, win_share=0.03)
        w = next(x for x in r_wide["winners"] if x["term"] == "magnesium bisglycinate 400mg")
        self.assertAlmostEqual(w["share"], 29_000_000 / 1_208_200_000, places=4)
        self.assertAlmostEqual(w["share"], 0.0240, places=4)
    def test_thresholds_are_parameters(self):
        r = misallocate.compute(self.t, self.c, min_conversions=1, win_cvr=0.02, win_share=0.5)
        self.assertIn("magnesium powder", {w["term"] for w in r["winners"]})
    def test_reallocation_and_render(self):
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
        self.assertTrue(any("dedicated" in x["proposal"] for x in r["reallocation"]))
        md = misallocate.render_md(r, "AUD")
        self.assertIn("Underfunded winners", md)
        self.assertIn("Overfunded losers", md)
    def test_winners_ranked_by_conversions_losers_by_cost(self):
        r = misallocate.compute(self.t, self.c)
        convs = [w["conversions"] for w in r["winners"]]
        self.assertEqual(convs, sorted(convs, reverse=True))
        costs = [l["cost"] for l in r["losers"]]
        self.assertEqual(costs, sorted(costs, reverse=True))
        # fixture losers have costs 1100, 900, 500 (x1,000,000 micros), so this order
        self.assertEqual([l["term"] for l in r["losers"]],
                         ["cheap magnesium tablets", "magnesium glycinate for sleep", "best sleep supplement"])
    def test_coverage_uses_term_cost_and_reported_campaign_cost(self):
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
        cov = {c["campaign"]: c for c in r["coverage"]}
        nb = cov["Search | NonBrand | BOF | Magnesium"]
        self.assertEqual(nb["term_cost"], 2_829_000_000)
        self.assertEqual(nb["campaign_cost"], 1_208_200_000)
        br = cov["Search | Brand | BOF | AU"]
        self.assertEqual(br["term_cost"], 498_000_000)
        self.assertEqual(br["campaign_cost"], 186_400_000)
    def test_render_states_denominator_ranking_and_coverage(self):
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
        md = misallocate.render_md(r, "AUD")
        self.assertIn("## Coverage", md)
        self.assertIn("ranked by conversions, losers by cost", md)
    def test_compute_result_is_json_serializable(self):
        r = misallocate.compute(self.t, self.c, windows=WINDOWS)
        json.dumps(r)

if __name__ == "__main__":
    unittest.main()
