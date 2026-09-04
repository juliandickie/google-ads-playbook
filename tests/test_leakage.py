import json, tempfile, unittest
from pathlib import Path
from gads_playbook import leakage, io
from gads_playbook.brand import Brand

WS = Path(__file__).parent / "fixtures" / "ws"

class LeakageTests(unittest.TestCase):
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.k = io.read_csv(WS / "exports" / "keywords.csv")
        self.b = Brand(["NordVital"])
    def test_per_campaign_split(self):
        r = leakage.compute(self.c, self.t, self.b, self.k)
        by = {x["campaign"]: x for x in r["per_campaign"]}
        nb = by["Search | NonBrand | BOF | Magnesium"]
        self.assertEqual(nb["kind"], "nonbrand")
        self.assertEqual(nb["branded_cost"], 300_000_000)      # nordvital magnesium glycinate
        self.assertEqual(nb["branded_value"], 2700.0)           # conversions_value is dollars, not micros
        self.assertEqual(nb["nonbranded_cost"], 2_529_000_000)  # 900+29+1100+500
        br = by["Search | Brand | BOF | AU"]
        self.assertEqual(br["kind"], "brand")
        self.assertEqual(br["nonbranded_cost"], 18_000_000)     # magnesium powder inside brand campaign
        pm = by["PMax | Scaling | Brand excluded"]
        self.assertEqual(pm["kind"], "pmax-scaling")
        self.assertEqual(pm["nonbranded_cost"], pm["cost"])
    def test_account_numbers_and_flag(self):
        r = leakage.compute(self.c, self.t, self.b, self.k)
        a = r["account"]
        # reported non-brand value comes from campaigns.csv: non-brand search 1080+900 and PMax scaling 903+855 over the 2 fixture days;
        # branded value inside it comes from search_terms.csv (nordvital magnesium glycinate, 2700)
        self.assertAlmostEqual(a["branded_share_of_nonbrand_value"], 2700 / (1980 + 1758), places=4)
        self.assertTrue(a["flag"])
        self.assertGreater(a["reported_nonbrand_roas"], a["true_new_customer_roas"])
        self.assertEqual(a["reverse_leak_cost"], 18_000_000)
        self.assertTrue(any("PMax" in s for s in r["assumptions"]))
    def test_render_and_cli(self):
        r = leakage.compute(self.c, self.t, self.b, self.k)
        md = leakage.render_md(r, "AUD")
        self.assertIn("True new-customer ROAS", md)
        self.assertIn("NonBrand", md)
        with tempfile.TemporaryDirectory() as d:
            import shutil
            ws = Path(d) / "ws"; shutil.copytree(WS, ws)
            from gads_playbook.cli import main
            self.assertEqual(main(["leakage", "--workspace", str(ws), "--run-date", "2026-09-04"]), 0)
            out = ws / "runs" / "2026-09-04"
            self.assertTrue((out / "leakage.md").exists())
            j = json.loads((out / "leakage.json").read_text())
            self.assertIn("account", j)
    def test_missing_brand_tokens_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            import shutil
            ws = Path(d) / "ws"; shutil.copytree(WS, ws)
            data = json.loads((ws / "gads.json").read_text())
            del data["brand_tokens"]
            (ws / "gads.json").write_text(json.dumps(data))
            from gads_playbook.cli import main
            self.assertEqual(main(["leakage", "--workspace", str(ws), "--run-date", "2026-09-04"]), 2)

if __name__ == "__main__":
    unittest.main()
