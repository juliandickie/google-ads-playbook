import contextlib, shutil, tempfile, unittest
from io import StringIO
from pathlib import Path
from gads_playbook import normalise, io, schema
from gads_playbook.cli import main as cli_main

FIX = Path(__file__).parent / "fixtures" / "ui"

class DetectTests(unittest.TestCase):
    def test_detects_by_title_line(self):
        self.assertEqual(normalise.detect_report(["Campaign report (Jul 1, 2026 - Sep 1, 2026)", "Day,Campaign"]), "campaigns")
        self.assertEqual(normalise.detect_report(["Search terms report (x)", "Search term,Campaign"]), "search_terms")
        self.assertEqual(normalise.detect_report(["Search keyword report (x)", "Keyword,Campaign"]), "keywords")
        self.assertEqual(normalise.detect_report(["Product report (x)", "Item ID,Title"]), "products")
        self.assertEqual(normalise.detect_report(["Conversion actions", "Conversion action,Category"]), "conversion_actions")
    def test_detects_by_header_when_no_title(self):
        self.assertEqual(normalise.detect_report(["Search term,Match type,Campaign,Cost"]), "search_terms")
        self.assertEqual(normalise.detect_report(["Day,Campaign,Cost,Conversions"]), "campaigns")
    def test_unknown_raises_with_types(self):
        with self.assertRaises(normalise.UnknownReport) as cm:
            normalise.detect_report(["Placement report (x)", "Placement,Impr."])
        self.assertIn("campaigns", str(cm.exception))
        # R35 (T3): only the five report types with a MAPPINGS entry are named; ad_groups has none.
        self.assertNotIn("ad_groups", str(cm.exception))

class FileTests(unittest.TestCase):
    def test_campaign_report(self):
        t, rows = normalise.normalise_file(FIX / "campaign_report.csv")
        self.assertEqual(t, "campaigns")
        self.assertEqual(len(rows), 6)  # totals row dropped
        r = rows[0]
        self.assertEqual(set(r), set(schema.COLUMNS["campaigns"]))
        self.assertEqual(r["segments.date"], "2026-08-30")
        self.assertEqual(r["campaign.name"], "Search | Brand | BOF | AU")
        self.assertEqual(r["campaign.status"], "ENABLED")
        self.assertEqual(r["campaign.advertising_channel_type"], "SEARCH")
        self.assertEqual(r["metrics.cost_micros"], "95400000")
        self.assertEqual(r["metrics.impressions"], "1200")
        self.assertEqual(r["metrics.conversions"], "30.0")
        self.assertEqual(r["metrics.conversions_value"], "2700.0")
        self.assertEqual(r["metrics.search_impression_share"], "0.9211")
        self.assertEqual(r["metrics.search_budget_lost_impression_share"], "0.1")
        self.assertEqual(r["metrics.search_rank_lost_impression_share"], "")
        self.assertEqual(rows[2]["campaign.advertising_channel_type"], "PERFORMANCE_MAX")
    def test_search_terms(self):
        t, rows = normalise.normalise_file(FIX / "search_terms_report.csv")
        self.assertEqual(t, "search_terms")
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["search_term_view.search_term"], "nordvital magnesium")
        self.assertEqual(rows[0]["segments.search_term_match_type"], "EXACT")
        self.assertEqual(rows[0]["metrics.cost_micros"], "270000000")
    def test_keywords_products_actions(self):
        t, rows = normalise.normalise_file(FIX / "keyword_report.csv")
        self.assertEqual((t, len(rows)), ("keywords", 2))
        self.assertEqual(rows[0]["ad_group_criterion.keyword.text"], "nordvital")
        self.assertEqual(rows[0]["ad_group_criterion.keyword.match_type"], "EXACT")
        self.assertEqual(rows[0]["ad_group_criterion.quality_info.quality_score"], "9")
        t, rows = normalise.normalise_file(FIX / "product_report.csv")
        self.assertEqual((t, len(rows)), ("products", 2))
        self.assertEqual(rows[0]["segments.product_item_id"], "MAG-120")
        t, rows = normalise.normalise_file(FIX / "conversion_actions.csv")
        self.assertEqual((t, len(rows)), ("conversion_actions", 3))
        self.assertEqual(rows[0]["conversion_action.primary_for_goal"], "true")
        self.assertEqual(rows[0]["conversion_action.click_through_lookback_window_days"], "30")
        self.assertEqual(rows[2]["conversion_action.phone_call_duration_seconds"], "0")
    def test_missing_required_column_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.csv"
            p.write_text("Campaign report (x)\nDay,Campaign,Clicks\n2026-08-30,A,1\n")
            with self.assertRaises(io.MissingInput) as cm:
                normalise.normalise_file(p)
            self.assertIn("Cost", str(cm.exception))
    def test_into_workspace_writes_canonical_files(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            out = normalise.normalise_into_workspace([FIX / "campaign_report.csv", FIX / "search_terms_report.csv"], ws)
            self.assertEqual(set(out), {"campaigns", "search_terms"})
            rows = io.read_csv(ws / "exports" / "campaigns.csv")
            self.assertEqual(list(rows[0].keys()), schema.COLUMNS["campaigns"])
            self.assertTrue((ws / "raw" / "campaign_report.csv").exists())
    def test_no_body_file_left_beside_fixture(self):
        normalise.normalise_file(FIX / "campaign_report.csv")
        self.assertFalse((FIX / "campaign_report.csv.body").exists())
    def test_unknown_report_names_the_file(self):
        with self.assertRaises(io.MissingInput) as cm:
            normalise.normalise_file(FIX / "unknown_report.csv")
        self.assertIsInstance(cm.exception, normalise.UnknownReport)
        self.assertIn("unknown_report.csv", str(cm.exception))
    def test_header_only_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "headeronly_bad.csv"
            p.write_text("Campaign report (x)\nDay,Campaign,Conversions,Conv. value\n")
            with self.assertRaises(io.MissingInput) as cm:
                normalise.normalise_file(p)
            self.assertIn("Cost", str(cm.exception))
    def test_header_only_all_required_columns_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "headeronly_ok.csv"
            p.write_text("Campaign report (x)\nDay,Campaign,Cost,Conversions,Conv. value\n")
            t, rows = normalise.normalise_file(p)
            self.assertEqual((t, rows), ("campaigns", []))
    def test_missing_path_names_it(self):
        with self.assertRaises(io.MissingInput) as cm:
            normalise.normalise_file(Path("/nonexistent/x.csv"))
        self.assertIn("x.csv", str(cm.exception))
    def test_tab_separated_export_normalises_correctly(self):
        # R35 (T3): io.sniff_delimiter is used for the header-line search too, so a genuinely
        # tab-separated export (with a comma inside the title line) still finds its header.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tab_campaign_report.csv"
            content = (
                "Campaign report (Jul 1, 2026 - Sep 1, 2026)\n"
                "Day\tCampaign\tCampaign state\tCampaign type\tBid strategy type\tBudget\tImpr.\tClicks\tCost\tConversions\tConv. value\tSearch impr. share\tSearch lost IS (budget)\tSearch lost IS (rank)\n"
                "2026-08-30\tSearch | Brand | BOF | AU\tEnabled\tSearch\tTarget impression share\t20.00\t1200\t300\t95.40\t30.00\t2700.00\t92.11%\t10.00%\t--\n"
                "2026-08-31\tSearch | Brand | BOF | AU\tEnabled\tSearch\tTarget impression share\t20.00\t1150\t290\t91.00\t28.00\t2520.00\t93.00%\t10.00%\t--\n"
            )
            p.write_text(content)
            t, rows = normalise.normalise_file(p)
            self.assertEqual(t, "campaigns")
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["campaign.name"], "Search | Brand | BOF | AU")
            self.assertEqual(rows[0]["metrics.cost_micros"], "95400000")
            self.assertEqual(rows[1]["metrics.cost_micros"], "91000000")

class MixedFolderTests(unittest.TestCase):
    def test_bad_file_in_batch_leaves_workspace_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            shutil.copy2(FIX / "campaign_report.csv", src / "campaign_report.csv")
            shutil.copy2(FIX / "unknown_report.csv", src / "unknown_report.csv")
            ws = Path(d) / "ws"
            with self.assertRaises(io.MissingInput):
                normalise.normalise_into_workspace([src / "campaign_report.csv", src / "unknown_report.csv"], ws)
            self.assertFalse((ws / "exports").exists() and any((ws / "exports").iterdir()))
            self.assertFalse((ws / "raw").exists() and any((ws / "raw").iterdir()))

class CliTests(unittest.TestCase):
    def test_unknown_report_via_cli_exits_2_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            code = cli_main(["normalise", str(FIX / "unknown_report.csv"), "--workspace", str(ws)])
            self.assertEqual(code, 2)
            self.assertFalse((ws / "exports").exists() and any((ws / "exports").iterdir()))
    def test_nonexistent_path_via_cli_exits_2_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            err = StringIO()
            with contextlib.redirect_stderr(err):
                code = cli_main(["normalise", "/nonexistent/export.csv", "--workspace", str(ws)])
            self.assertEqual(code, 2)
            self.assertFalse(any(ws.iterdir()))
    def test_empty_directory_via_cli_exits_2_and_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty"
            empty.mkdir()
            ws = Path(d) / "ws"
            err = StringIO()
            with contextlib.redirect_stderr(err):
                code = cli_main(["normalise", str(empty), "--workspace", str(ws)])
            self.assertEqual(code, 2)
            self.assertIn(str(empty), err.getvalue())
            self.assertFalse(ws.exists() and any(ws.iterdir()))

if __name__ == "__main__":
    unittest.main()
