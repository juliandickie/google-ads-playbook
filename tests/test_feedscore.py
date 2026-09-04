import unittest
from pathlib import Path
from gads_playbook import feedscore, io

FEED = Path(__file__).parent / "fixtures" / "feed.tsv"

class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.rows = io.read_csv(FEED)
        self.by = {r["id"]: r for r in self.rows}
    def test_full_marks_with_reviews(self):
        score, missing, checks = feedscore.score_product(self.by["MAG-120"], brand_hint="NordVital", reviews=True)
        self.assertEqual(score, 10, missing)
    def test_reviews_unknown_withholds_point(self):
        score, missing, checks = feedscore.score_product(self.by["MAG-120"], brand_hint="NordVital", reviews=None)
        self.assertEqual(score, 9)
        self.assertIn("reviews (unknown, pass --reviews-integrated)", missing)
    def test_thin_product(self):
        score, missing, checks = feedscore.score_product(self.by["ZNC-60"], brand_hint="NordVital", reviews=True)
        self.assertLessEqual(score, 3)
        for m in ("title", "description", "images", "category", "product_type", "gtin", "sale pricing", "shipping", "custom labels"):
            self.assertTrue(any(x.startswith(m) for x in missing), m)
    def test_sale_pricing_rule(self):
        s, m, c = feedscore.score_product(self.by["OMG-90"], brand_hint="NordVital", reviews=True)
        self.assertTrue(c["sale pricing"])   # sale price with effective date
        s, m, c = feedscore.score_product(self.by["ZNC-60"], brand_hint="NordVital", reviews=True)
        self.assertFalse(c["sale pricing"])  # sale price without effective date
        s, m, c = feedscore.score_product(self.by["VTD-100"], brand_hint="NordVital", reviews=True)
        self.assertTrue(c["sale pricing"])   # no sale at all is fine
    def test_category_depth(self):
        s, m, c = feedscore.score_product(self.by["OMG-90"], brand_hint="NordVital", reviews=True)
        self.assertTrue(c["category"])       # three levels
        s, m, c = feedscore.score_product(self.by["ZNC-60"], brand_hint="NordVital", reviews=True)
        self.assertFalse(c["category"])      # one level
        s, m, c = feedscore.score_product(self.by["MAG-120"], brand_hint="NordVital", reviews=True)
        self.assertTrue(c["category"])       # numeric id
    def test_compute_ranks_by_revenue_and_lists_rebuilds(self):
        products = [{"segments.product_item_id": "ZNC-60", "metrics.conversions_value": "45.0"},
                    {"segments.product_item_id": "MAG-120", "metrics.conversions_value": "1758.0"}]
        r = feedscore.compute(self.rows, products, reviews=True, top_n=1, brand_hint="NordVital")
        self.assertEqual(r["products"][0]["id"], "MAG-120")
        self.assertTrue(r["products"][0]["ranked"])
        self.assertIn("ZNC-60", r["rebuild"])
        self.assertIn("CRE-300", r["rebuild"])
        md = feedscore.render_md(r)
        self.assertIn("Rebuild candidates", md)

if __name__ == "__main__":
    unittest.main()
