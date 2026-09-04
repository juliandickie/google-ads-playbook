import unittest
from pathlib import Path
from gads_playbook import ceiling, io
from gads_playbook.brand import Brand

KP = Path(__file__).parent / "fixtures" / "keyword_planner.csv"

class CeilingTests(unittest.TestCase):
    def setUp(self):
        self.rows = io.read_csv(KP)
        self.b = Brand(["NordVital"])
    def test_blocks(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        self.assertEqual(r["brand"]["volume"], 7000)
        self.assertEqual(r["nonbrand"]["volume"], 90000)
        self.assertAlmostEqual(r["brand"]["clicks"], 1400)
        self.assertAlmostEqual(r["brand"]["purchases"], 140)
        self.assertAlmostEqual(r["brand"]["revenue"], 140 * 88)
        self.assertAlmostEqual(r["nonbrand"]["clicks"], 3600)
        self.assertAlmostEqual(r["nonbrand"]["purchases"], 72)
    def test_cpc_midpoint_and_overrides(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        # brand cpc = volume-weighted midpoint: (5000*0.40 + 2000*0.55) / 7000
        self.assertAlmostEqual(r["brand"]["cpc"], (5000 * 0.40 + 2000 * 0.55) / 7000, places=4)
        r2 = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6, brand_cpc=0.10, nb_cpc=1.50)
        self.assertAlmostEqual(r2["brand"]["media_cost"], 1400 * 0.10)
        self.assertAlmostEqual(r2["nonbrand"]["media_cost"], 3600 * 1.50)
        self.assertAlmostEqual(r2["brand"]["profit"], 140 * 88 * 0.6 - 140)
    def test_assumptions_listed_and_render(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        self.assertTrue(any("20" in a and "CTR" in a for a in r["assumptions"]))
        md = ceiling.render_md(r, "AUD")
        self.assertIn("ceiling, not a forecast", md)

if __name__ == "__main__":
    unittest.main()
