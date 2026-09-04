import contextlib, json, tempfile, unittest
from io import StringIO
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
            buf = StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["leakage", "--workspace", str(ws), "--run-date", "2026-09-04"])
            self.assertEqual(code, 0)
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

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.k = io.read_csv(WS / "exports" / "keywords.csv")
        self.b = Brand(["NordVital"])
        # matches tests/fixtures/ws/gads.json
        self.differing_windows = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-03-04"}
    def test_differing_windows_flag_the_mismatch(self):
        r = leakage.compute(self.c, self.t, self.b, self.k, windows=self.differing_windows)
        self.assertTrue(any("mix the two windows" in s for s in r["assumptions"]))
        md = leakage.render_md(r, "AUD")
        self.assertIn("Search terms window 2026-03-04 to 2026-08-31", md)
    def test_matching_windows_add_no_assumption(self):
        matching = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-06-03"}
        r = leakage.compute(self.c, self.t, self.b, self.k, windows=matching)
        self.assertFalse(any("mix the two windows" in s for s in r["assumptions"]))
    def test_empty_search_terms_reports_the_other_spend_gap(self):
        r = leakage.compute(self.c, [], self.b)
        search_campaigns = [p for p in r["per_campaign"] if p["kind"] in ("brand", "nonbrand")]
        self.assertTrue(search_campaigns)
        for p in search_campaigns:
            self.assertEqual(p["other_cost"], p["cost"])
        self.assertTrue(any("privacy threshold" in s for s in r["assumptions"]))
    def test_default_keywords_none_still_classifies_by_name(self):
        r = leakage.compute(self.c, self.t, self.b, keywords=None)
        by = {x["campaign"]: x for x in r["per_campaign"]}
        self.assertEqual(by["Search | Brand | BOF | AU"]["kind"], "brand")

class OtherChannelTests(unittest.TestCase):
    # R32: a non-search, non-shopping, non-PMax campaign (Display, Video, Demand Gen, Multi-channel) is not
    # split by search terms or folded into the non-brand group; it gets its own kind and its own section.
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.k = io.read_csv(WS / "exports" / "keywords.csv")
        self.b = Brand(["NordVital"])
        self.display_row = {"segments.date": "2026-08-30", "campaign.id": "", "campaign.name": "Display | Remarketing",
                             "campaign.status": "ENABLED", "campaign.advertising_channel_type": "DISPLAY",
                             "campaign.bidding_strategy_type": "MAXIMIZE_CONVERSIONS", "campaign_budget.amount_micros": "10000000",
                             "metrics.impressions": "50000", "metrics.clicks": "200", "metrics.cost_micros": "5000000",
                             "metrics.conversions": "2.0", "metrics.conversions_value": "300.0",
                             "metrics.search_impression_share": "", "metrics.search_budget_lost_impression_share": "",
                             "metrics.search_rank_lost_impression_share": ""}
    def test_display_campaign_is_other_channel_and_excluded_from_nonbrand_roas(self):
        r_before = leakage.compute(self.c, self.t, self.b, self.k)
        r_after = leakage.compute(self.c + [self.display_row], self.t, self.b, self.k)
        self.assertAlmostEqual(r_before["account"]["reported_nonbrand_roas"], r_after["account"]["reported_nonbrand_roas"])
        by = {x["campaign"]: x for x in r_after["per_campaign"]}
        self.assertEqual(by["Display | Remarketing"]["kind"], "other-channel")
        self.assertAlmostEqual(r_after["account"]["total_value"] - r_before["account"]["total_value"], 300.0)
        privacy_assumptions = [s for s in r_after["assumptions"] if "privacy threshold" in s]
        for s in privacy_assumptions:
            self.assertNotIn("Display | Remarketing", s)
    def test_other_channel_section_and_assumption(self):
        r = leakage.compute(self.c + [self.display_row], self.t, self.b, self.k)
        md = leakage.render_md(r, "AUD")
        self.assertIn("## Other channels", md)
        self.assertIn("Display | Remarketing", md)
        self.assertTrue(any("Non-search campaigns" in s and "Display | Remarketing" in s for s in r["assumptions"]))

class TermsOnlyTests(unittest.TestCase):
    # R33: a campaign present in search_terms.csv but absent from campaigns.csv is a phantom row, not a
    # real zero-cost campaign; it must not inflate the account totals or the non-brand grouping.
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.k = io.read_csv(WS / "exports" / "keywords.csv")
        self.b = Brand(["NordVital"])
        self.ghost_row = {"campaign.id": "", "campaign.name": "Ghost", "ad_group.id": "", "ad_group.name": "",
                           "search_term_view.search_term": "ghost term", "segments.search_term_match_type": "BROAD",
                           "metrics.impressions": "100", "metrics.clicks": "10", "metrics.cost_micros": "900000",
                           "metrics.conversions": "1.0", "metrics.conversions_value": "50.0"}
    def test_ghost_campaign_is_terms_only_and_excluded_from_blended_roas(self):
        r_before = leakage.compute(self.c, self.t, self.b, self.k)
        r_after = leakage.compute(self.c, self.t + [self.ghost_row], self.b, self.k)
        self.assertAlmostEqual(r_before["account"]["blended_roas"], r_after["account"]["blended_roas"])
        by = {x["campaign"]: x for x in r_after["per_campaign"]}
        self.assertEqual(by["Ghost"]["kind"], "terms-only")
        self.assertEqual(by["Ghost"]["cost"], 900_000)
        self.assertAlmostEqual(by["Ghost"]["value"], 50.0)
        self.assertTrue(any("Ghost" in s and "not in campaigns.csv" in s for s in r_after["assumptions"]))
    def test_terms_only_other_cost_is_none_and_assumption_is_singular(self):
        # Residual fix (2026-09-04): a terms-only row has no campaigns.csv row to subtract from, so
        # other_cost is always None (never a misleading 0.00), and a single ghost campaign reads
        # "appears" (not "appear").
        r = leakage.compute(self.c, self.t + [self.ghost_row], self.b, self.k)
        by = {x["campaign"]: x for x in r["per_campaign"]}
        self.assertIsNone(by["Ghost"]["other_cost"])
        md = leakage.render_md(r, "AUD")
        ghost_line = next(line for line in md.splitlines() if line.startswith("| Ghost |"))
        self.assertTrue(ghost_line.rstrip().endswith("| n/a |"))
        self.assertTrue(any("Ghost appears in search terms" in s for s in r["assumptions"]))
    def test_multiple_terms_only_campaigns_use_plural_assumption(self):
        second_ghost = dict(self.ghost_row, **{"campaign.name": "Ghost2", "search_term_view.search_term": "second ghost term"})
        r = leakage.compute(self.c, self.t + [self.ghost_row, second_ghost], self.b, self.k)
        self.assertTrue(any("Ghost, Ghost2 appear in search terms" in s for s in r["assumptions"]))

class WindowMismatchOtherCostTests(unittest.TestCase):
    # R34: when the campaign and search-terms windows differ, other_cost is unknowable (not zero), so it
    # must render as an explicit "n/a" rather than a number that looks precise but mixes two windows.
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
        self.t = io.read_csv(WS / "exports" / "search_terms.csv")
        self.k = io.read_csv(WS / "exports" / "keywords.csv")
        self.b = Brand(["NordVital"])
        self.differing_windows = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-03-04"}
        self.matching_windows = {"window_start": "2026-06-03", "window_end": "2026-08-31", "search_terms_window_start": "2026-06-03"}
    def test_other_cost_is_none_and_renders_na_when_windows_differ(self):
        r = leakage.compute(self.c, self.t, self.b, self.k, windows=self.differing_windows)
        by = {x["campaign"]: x for x in r["per_campaign"]}
        nb = by["Search | NonBrand | BOF | Magnesium"]
        self.assertIsNone(nb["other_cost"])
        md = leakage.render_md(r, "AUD")
        self.assertIn("n/a (windows differ)", md)
        self.assertFalse(any("privacy threshold" in s for s in r["assumptions"]))
    def test_other_cost_computed_when_windows_match(self):
        r = leakage.compute(self.c, self.t, self.b, self.k, windows=self.matching_windows)
        by = {x["campaign"]: x for x in r["per_campaign"]}
        nb = by["Search | NonBrand | BOF | Magnesium"]
        self.assertIsNotNone(nb["other_cost"])
        self.assertEqual(nb["other_cost"], max(nb["cost"] - nb["branded_cost"] - nb["nonbranded_cost"], 0))

if __name__ == "__main__":
    unittest.main()
