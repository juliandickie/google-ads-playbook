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

def _synthetic_feed_products(n):
    rows = []
    for i in range(n):
        rows.append({"id": f"P{i:02d}", "title": f"Product {i}", "description": "short",
                     "image_link": "", "additional_image_link": "", "google_product_category": "",
                     "product_type": "", "gtin": "", "sale_price": "", "sale_price_effective_date": "",
                     "shipping": "", "shipping_weight": "", "custom_label_0": "", "custom_label_1": ""})
    return rows

class RenderCapTests(unittest.TestCase):
    # R36: render_md must not dump every product into the markdown; cap it at the ranked top_n plus the
    # top_n lowest scorers, and point to feedscore.json (which keeps everything) for the rest.
    def setUp(self):
        self.rows = io.read_csv(FEED)
    def test_render_caps_rows_and_names_the_overflow(self):
        feed_rows = _synthetic_feed_products(25)
        product_rows = [{"segments.product_item_id": f"P{i:02d}", "metrics.conversions_value": str(100 - i)} for i in range(5)]
        r = feedscore.compute(feed_rows, product_rows, reviews=True, top_n=5, brand_hint="NordVital")
        self.assertEqual(r["scored"], 25)
        md = feedscore.render_md(r)
        row_lines = [l for l in md.splitlines() if l.startswith("| P")]
        self.assertLessEqual(len(row_lines), 10)
        self.assertIn("and 20 more in feedscore.json", md)
        self.assertIn("Score distribution", md)
    def test_missing_from_feed_lists_products_csv_only_ids(self):
        feed_rows = _synthetic_feed_products(3)
        product_rows = [{"segments.product_item_id": "GHOST-1", "metrics.conversions_value": "500.0"},
                        {"segments.product_item_id": "P00", "metrics.conversions_value": "10.0"}]
        r = feedscore.compute(feed_rows, product_rows, reviews=True, top_n=5, brand_hint="NordVital")
        self.assertIn("GHOST-1", r["missing_from_feed"])
        self.assertNotIn("P00", r["missing_from_feed"])
        md = feedscore.render_md(r)
        self.assertIn("## In products.csv but not in the feed", md)
        self.assertIn("GHOST-1", md)
    def test_missing_from_feed_none_renders_none(self):
        r = feedscore.compute(self.rows, product_rows=None, reviews=True, top_n=5, brand_hint="NordVital")
        self.assertEqual(r["missing_from_feed"], [])
        md = feedscore.render_md(r)
        section = md.split("## In products.csv but not in the feed", 1)[1]
        self.assertIn("None.", section)

if __name__ == "__main__":
    unittest.main()
