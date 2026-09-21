import contextlib, csv, json, os, re, tempfile, unittest, urllib.parse
from io import StringIO
from pathlib import Path
from gads_playbook import audit, cli

RUN = "2026-09-15"
DEEP = "2026-09-15"

def write_csv(path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

def camp_row(name, day, cost, conv, value, status="ENABLED", strategy="MAXIMIZE_CONVERSIONS", channel="SEARCH", cid=1):
    return {"segments.date": day, "campaign.id": cid, "campaign.name": name, "campaign.status": status, "campaign.advertising_channel_type": channel,
            "campaign.bidding_strategy_type": strategy, "campaign_budget.amount_micros": 50_000_000, "metrics.impressions": 1000, "metrics.clicks": 100,
            "metrics.cost_micros": cost, "metrics.conversions": conv, "metrics.conversions_value": value,
            "metrics.search_impression_share": 0.5, "metrics.search_budget_lost_impression_share": 0.0, "metrics.search_rank_lost_impression_share": 0.4}

CAMP_COLS = list(camp_row("x", "2026-01-01", 0, 0, 0).keys())
TERM_COLS = ["campaign.id", "campaign.name", "ad_group.id", "ad_group.name", "search_term_view.search_term", "segments.search_term_match_type",
             "metrics.impressions", "metrics.clicks", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value"]
KW_COLS = ["campaign.id", "campaign.name", "ad_group.id", "ad_group.name", "ad_group_criterion.criterion_id", "ad_group_criterion.keyword.text",
           "ad_group_criterion.keyword.match_type", "ad_group_criterion.status", "ad_group_criterion.quality_info.quality_score",
           "metrics.impressions", "metrics.clicks", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value"]
CA_COLS = ["conversion_action.id", "conversion_action.name", "conversion_action.category", "conversion_action.type", "conversion_action.status",
           "conversion_action.primary_for_goal", "conversion_action.counting_type", "conversion_action.click_through_lookback_window_days",
           "conversion_action.view_through_lookback_window_days", "conversion_action.attribution_model_settings.attribution_model",
           "conversion_action.include_in_conversions_metric", "conversion_action.phone_call_duration_seconds", "conversion_action.value_settings.default_value"]

def minimal_ws(d):
    ws = Path(d)
    (ws / "gads.json").write_text(json.dumps({"customer_id": "1234567890", "customer_name": "Example Co", "currency": "AUD", "timezone": "Australia/Brisbane",
                                              "window_start": "2026-03-19", "window_end": "2026-09-14", "brand_tokens": ["Example Co"], "target_roas": 4.0, "breakeven_roas": 1.25}))
    write_csv(ws / "exports" / "campaigns.csv", [camp_row("Search | Widgets | AU", "2026-09-01", 100_000_000, 10, 800.0),
                                                  camp_row("Search | Widgets | NZ", "2026-09-01", 50_000_000, 20, 200.0, strategy="TARGET_SPEND", cid=2)], CAMP_COLS)
    return ws

def full_ws(d):
    ws = minimal_ws(d)
    write_csv(ws / "exports" / "search_terms.csv", [
        {"campaign.name": "Search | Widgets | AU", "search_term_view.search_term": "free widgets", "metrics.cost_micros": 30_000_000, "metrics.conversions": 0},
        {"campaign.name": "Search | Widgets | AU", "search_term_view.search_term": "buy widgets", "metrics.cost_micros": 40_000_000, "metrics.conversions": 5},
        {"campaign.name": "Search | Widgets | NZ", "search_term_view.search_term": "example co widgets", "metrics.cost_micros": 5_000_000, "metrics.conversions": 1}], TERM_COLS)
    write_csv(ws / "exports" / "keywords.csv", [{"campaign.name": "Search | Widgets | AU", "ad_group_criterion.keyword.text": "widgets", "ad_group_criterion.keyword.match_type": "PHRASE",
                                                 "ad_group_criterion.status": "ENABLED", "metrics.clicks": 150, "metrics.cost_micros": 90_000_000, "metrics.conversions": 0}], KW_COLS)
    write_csv(ws / "exports" / "conversion_actions.csv", [
        {"conversion_action.id": 1, "conversion_action.name": "Purchase upload", "conversion_action.category": "PURCHASE", "conversion_action.type": "UPLOAD_CLICKS", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": "true", "conversion_action.click_through_lookback_window_days": 90, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN"},
        {"conversion_action.id": 2, "conversion_action.name": "Signup", "conversion_action.category": "SIGNUP", "conversion_action.type": "WEBPAGE", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": "true", "conversion_action.click_through_lookback_window_days": 30, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_ADS_LAST_CLICK"},
        {"conversion_action.id": 3, "conversion_action.name": "Old goal", "conversion_action.category": "PAGE_VIEW", "conversion_action.type": "UNIVERSAL_ANALYTICS_GOAL", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": "false", "conversion_action.click_through_lookback_window_days": 30, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_ADS_LAST_CLICK"}], CA_COLS)
    run = ws / "runs" / RUN
    run.mkdir(parents=True)
    (run / "leakage.json").write_text(json.dumps({"per_campaign": [{"campaign": "Search | Widgets | NZ", "kind": "nonbrand", "cost": 50_000_000, "conversions": 20, "value": 200.0, "branded_cost": 5_000_000, "branded_value": 50.0, "nonbranded_cost": 45_000_000, "nonbranded_value": 150.0, "other_cost": 0}],
                                                  "account": {"blended_roas": 6.67, "reported_nonbrand_roas": 6.67, "branded_share_of_nonbrand_value": 0.05, "true_new_customer_roas": 6.3, "reverse_leak_cost": 0}, "assumptions": ["Leakage is a floor."]}))
    (run / "misallocation.json").write_text(json.dumps({"winners": [], "losers": [], "thresholds": {"min_conversions": 5, "win_cvr": 0.2, "win_share": 0.02, "lose_cvr": 0.03, "lose_share": 0.05},
                                                        "coverage": [{"campaign": "Search | Widgets | AU", "term_cost": 70_000_000, "campaign_cost": 100_000_000}]}))
    (run / "windows.json").write_text(json.dumps({"end_date": "2026-09-14", "target_roas": 4.0, "breakeven_roas": 1.25, "account": {"windows": {"30": {"cur": {"cost": 150_000_000, "conversions": 30, "value": 1000.0, "roas": 6.67, "cpa": 5.0}, "prior": {"cost": 100_000_000, "conversions": 10, "value": 300.0, "roas": 3.0, "cpa": 10.0}, "delta_roas": 1.22}}},
                                                  "campaigns": [{"campaign": "Search | Widgets | AU", "verdict": "scale", "reasons": ["all windows above target"], "budget_limited": False, "rank_lost_7d": 0.4, "step": "raise budget 20 percent",
                                                                 "windows": {"7": {"cur": {"cost": 10_000_000, "conversions": 2, "value": 100.0, "roas": 10.0, "cpa": 5.0}, "prior": {"cost": 1, "conversions": 0, "value": 0, "roas": 0, "cpa": None}, "delta_roas": None},
                                                                             "30": {"cur": {"cost": 100_000_000, "conversions": 10, "value": 800.0, "roas": 8.0, "cpa": 10.0}, "prior": {"cost": 1, "conversions": 0, "value": 0, "roas": 0, "cpa": None}, "delta_roas": None}}},
                                                                {"campaign": "Search | Widgets | NZ", "verdict": "hold", "reasons": ["under target"], "budget_limited": True, "rank_lost_7d": 0.1, "step": "no budget change", "windows": {}}]}))
    (ws / "runs" / "2026-09-05").mkdir()
    (ws / "runs" / "2026-09-05" / "brand-serp.md").write_text("# Brand SERP\n\n| phrase | country | rank | paid | verdict |\n| example co | AU | 1 | none | no bid |\n")
    deep = ws / "raw" / f"deep-{DEEP}"
    deep.mkdir(parents=True)
    files = {
        "manifest.json": {"run_date": DEEP, "windows": {"metrics": ["2026-06-17", "2026-09-14"], "quality": ["2026-08-16", "2026-09-14"], "changes": ["2026-08-19", "2026-09-15"]}, "queries": {"geo_90d": {"error": "rejected", "file": "geo_90d.error.txt"}}},
        "campaign_settings.json": [{"campaign.name": "Search | Widgets | AU", "campaign.status": "ENABLED", "campaign.bidding_strategy_type": "MAXIMIZE_CONVERSIONS", "campaign.maximize_conversions.target_cpa_micros": 8_000_000, "campaign_budget.amount_micros": 50_000_000, "campaign.network_settings.target_partner_search_network": False, "campaign.geo_target_type_setting.positive_geo_target_type": "PRESENCE", "campaign.primary_status": "ELIGIBLE", "campaign.primary_status_reasons": []},
                                   {"campaign.name": "Search | Widgets | NZ", "campaign.status": "ENABLED", "campaign.bidding_strategy_type": "TARGET_SPEND", "campaign_budget.amount_micros": 30_000_000, "campaign.network_settings.target_partner_search_network": False, "campaign.geo_target_type_setting.positive_geo_target_type": "PRESENCE", "campaign.primary_status": "LIMITED", "campaign.primary_status_reasons": ["HAS_ADS_LIMITED_BY_POLICY"]}],
        "campaign_criteria.json": [{"campaign.name": "Search | Widgets | AU", "campaign_criterion.type": "LOCATION", "campaign_criterion.negative": False, "campaign_criterion.location.geo_target_constant": "geoTargetConstants/2036", "campaign_criterion.device.type": "", "campaign_criterion.bid_modifier": 0.0},
                                   {"campaign.name": "Search | Widgets | NZ", "campaign_criterion.type": "LOCATION", "campaign_criterion.negative": False, "campaign_criterion.location.geo_target_constant": "geoTargetConstants/2036", "campaign_criterion.device.type": "", "campaign_criterion.bid_modifier": 0.0},
                                   {"campaign.name": "Search | Widgets | NZ", "campaign_criterion.type": "DEVICE", "campaign_criterion.negative": False, "campaign_criterion.location.geo_target_constant": "", "campaign_criterion.device.type": "MOBILE", "campaign_criterion.bid_modifier": 0.0}],
        "ad_policy_topics.json": [{"campaign.name": "Search | Widgets | NZ", "ad_group.name": "Core", "ad_group_ad.policy_summary.approval_status": "APPROVED_LIMITED", "ad_group_ad.policy_summary.policy_topic_entries": [{"topic": "CAPITALIZATION"}]}],
        "ads.json": [{"campaign.name": "Search | Widgets | AU", "ad_group.name": "Core", "ad_group_ad.ad_strength": "GOOD"}, {"campaign.name": "Search | Widgets | NZ", "ad_group.name": "Core", "ad_group_ad.ad_strength": "POOR"}],
        "shared_sets.json": [{"campaign.name": "Search | Widgets | AU", "shared_set.name": "Generic negatives", "shared_set.type": "NEGATIVE_KEYWORDS", "shared_set.member_count": 120}],
        "campaign_audiences.json": [], "adgroup_audiences.json": [],
        "user_lists.json": [{"user_list.name": "All buyers", "user_list.size_for_search": 5000, "user_list.membership_status": "OPEN"}, {"user_list.name": "Tiny", "user_list.size_for_search": 10}],
        "conversion_actions_full.json": [{"conversion_action.id": 1, "conversion_action.name": "Purchase upload", "conversion_action.category": "PURCHASE", "conversion_action.type": "UPLOAD_CLICKS", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": True, "conversion_action.click_through_lookback_window_days": 90, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN", "conversion_action.value_settings.always_use_default_value": False},
                                         {"conversion_action.id": 2, "conversion_action.name": "Signup", "conversion_action.category": "SIGNUP", "conversion_action.type": "WEBPAGE", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": True, "conversion_action.click_through_lookback_window_days": 30, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_ADS_LAST_CLICK", "conversion_action.value_settings.always_use_default_value": True},
                                         {"conversion_action.id": 3, "conversion_action.name": "Old goal", "conversion_action.category": "PAGE_VIEW", "conversion_action.type": "UNIVERSAL_ANALYTICS_GOAL", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": False, "conversion_action.click_through_lookback_window_days": 30, "conversion_action.attribution_model_settings.attribution_model": "GOOGLE_ADS_LAST_CLICK", "conversion_action.value_settings.always_use_default_value": False},
                                         {"conversion_action.id": 4, "conversion_action.name": "GA4 purchase", "conversion_action.category": "PURCHASE", "conversion_action.type": "GOOGLE_ANALYTICS_4_PURCHASE", "conversion_action.status": "ENABLED", "conversion_action.primary_for_goal": False, "conversion_action.click_through_lookback_window_days": 90, "conversion_action.attribution_model_settings.attribution_model": "UNKNOWN", "conversion_action.value_settings.always_use_default_value": False}],
        "conversion_action_metrics_90d.json": [{"conversion_action.id": 1, "conversion_action.name": "Purchase upload", "metrics.all_conversions": 20.0, "metrics.all_conversions_value": 900.0},
                                               {"conversion_action.id": 2, "conversion_action.name": "Signup", "metrics.all_conversions": 60.0, "metrics.all_conversions_value": 0.0},
                                               {"conversion_action.id": 3, "conversion_action.name": "Old goal", "metrics.all_conversions": 0.0, "metrics.all_conversions_value": 0.0},
                                               {"conversion_action.id": 4, "conversion_action.name": "GA4 purchase", "metrics.all_conversions": 0.0, "metrics.all_conversions_value": 0.0}],
        "customer_conversion_goals.json": [{"customer_conversion_goal.category": "PURCHASE", "customer_conversion_goal.biddable": True}, {"customer_conversion_goal.category": "SIGNUP", "customer_conversion_goal.biddable": True}],
        "customer.json": [{"customer.auto_tagging_enabled": True, "customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled": True, "customer.conversion_tracking_setting.conversion_tracking_status": "CONVERSION_TRACKING_MANAGED_BY_SELF"}],
        "device_90d.json": [{"campaign.name": "Search | Widgets | NZ", "segments.device": "DESKTOP", "metrics.cost_micros": 20_000_000, "metrics.conversions": 10.0},
                            {"campaign.name": "Search | Widgets | NZ", "segments.device": "MOBILE", "metrics.cost_micros": 20_000_000, "metrics.conversions": 2.0}],
        "keyword_quality_30d.json": [{"ad_group_criterion.quality_info.quality_score": 8, "metrics.impressions": 100}, {"ad_group_criterion.quality_info.quality_score": 3, "metrics.impressions": 10}],
        "landing_pages_90d.json": [{"campaign.name": "Search | Widgets | AU", "landing_page_view.unexpanded_final_url": "https://example.com/widgets", "metrics.cost_micros": 90_000_000, "metrics.conversions": 9.0},
                                   {"campaign.name": "Search | Widgets | AU", "landing_page_view.unexpanded_final_url": "https://example.com/", "metrics.cost_micros": 10_000_000, "metrics.conversions": 0.0}],
        "change_events_28d.json": [],
        "customer_assets.json": [{"customer_asset.field_type": "SITELINK"}], "campaign_assets.json": [], "adgroup_assets.json": [],
    }
    for name, content in files.items():
        (deep / name).write_text(json.dumps(content))
    (deep / "geo_90d.error.txt").write_text("rejected")
    return ws

def rec_titles(rep):
    return [r["title"] for r in rep.recs]

class ChecklistTests(unittest.TestCase):
    def test_parses_controls_from_the_shipped_reference(self):
        controls = audit.parse_checklist()
        ids = {c[1] for c in controls}
        self.assertIn("G42", ids); self.assertIn("G-CT1", ids); self.assertIn("G61", ids)
        self.assertTrue(all(c[0] for c in controls))

class MinimalEvidenceTests(unittest.TestCase):
    def test_runs_with_only_campaigns_and_names_every_gap(self):
        with tempfile.TemporaryDirectory() as d:
            ws = minimal_ws(d)
            rep, out = audit.run(ws, RUN)
            text = (out / "audit.md").read_text()
            self.assertIn("## Missing evidence", text)
            self.assertIn("raw/deep-<date>/", text)
            self.assertIn("run gads leakage", text)
            self.assertIn("no evidence", text)
            self.assertEqual(rep.controls["G06"][0], "fail")
            self.assertEqual(rep.controls["G42"][0], "no evidence")
            self.assertTrue((out / "audit.json").exists())
            self.assertFalse((out / "audit-executive.md").exists())

class FullEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = full_ws(self.tmp.name)
        self.rep, self.out = audit.run(self.ws, RUN, executive=True)
        self.text = (self.out / "audit.md").read_text()
        self.exec = (self.out / "audit-executive.md").read_text()
    def tearDown(self):
        self.tmp.cleanup()
    def test_tracking_rules(self):
        titles = rec_titles(self.rep)
        self.assertIn("One primary action, the purchase", titles)
        self.assertIn("Remove the actions that cannot fire", titles)
        self.assertIn("Matched windows and attribution", titles)
        self.assertIn("The GA4 purchase import records zero", titles)
        self.assertEqual(self.rep.controls["G47"][0], "fail")
        self.assertEqual(self.rep.controls["G46"][0], "warning")   # the 30-day signup is primary even though the purchase fired at 90
        self.assertEqual(self.rep.controls["G49"][0], "warning")
        self.assertEqual(self.rep.controls["G-CT2"][0], "warning")
        self.assertEqual(self.rep.controls["G43"][0], "partial")
        self.assertEqual(self.rep.controls["G44"][0], "pass")
        one = next(r for r in self.rep.recs if r["title"] == "One primary action, the purchase")
        self.assertIn('"Purchase upload"', one["Change"])
        self.assertIn("Search | Widgets | AU", one["Change"])   # the Maximize Conversions campaign moves to value bidding
        self.assertEqual(self.rep.headline["purchases_90d"], 20.0)
    def test_leakage_uses_the_earlier_serp_check(self):
        self.assertIn("from the 2026-09-05 run", self.text)
        brand = next(r for r in self.rep.recs if r["title"].startswith("Brand negatives"))
        self.assertEqual(brand["Confidence"], "high")
        self.assertIn("runs/2026-09-05/brand-serp.md", brand["Evidence"])
    def test_structure_rules(self):
        titles = rec_titles(self.rep)
        self.assertIn("Clear the CAPITALIZATION policy limit", titles)
        self.assertIn("Rebuild the Poor-strength ads", titles)
        self.assertIn("Search | Widgets | NZ onto a strategy that can see money", titles)
        self.assertIn('"Generic negatives" on every campaign', titles)
        self.assertIn("Observation audiences on every campaign", titles)
        self.assertIn("Mobile bid adjustment on Search | Widgets | NZ", titles)
        self.assertIn("One auction per market for Search | Widgets | AU and Search | Widgets | NZ", titles)
        self.assertIn("Search Partners on one campaign", titles)
        self.assertEqual(self.rep.controls["G13"][0], "fail")
        self.assertEqual(self.rep.controls["G16"][0], "fail")     # 30 of 75 visible spend on a zero-conversion term
        self.assertEqual(self.rep.controls["G-WS1"][0], "warning")
        self.assertEqual(self.rep.controls["G39"][0], "warning")  # NZ is budget-limited
        self.assertEqual(self.rep.controls["G08"][0], "fail")
        self.assertEqual(self.rep.controls["G21"][0], "warning")
    def test_missing_deep_query_is_a_named_gap(self):
        self.assertIn("geo_90d.error.txt", self.text)
    def test_numbering_and_order(self):
        sections = [r["section"] for r in self.rep.recs]
        self.assertEqual(sections, sorted(sections, key=["tracking", "leakage", "pmax", "misallocation", "feed", "roles"].index))
        self.assertEqual([r["number"] for r in self.rep.recs], list(range(1, len(self.rep.recs) + 1)))
        three = audit.three_changes(self.rep)
        self.assertEqual(three[0]["section"], "tracking")
        self.assertIn("strategy", three[1]["title"])
    def test_document_layout_and_links(self):
        self.assertNotIn("\n- ", self.text)
        self.assertFalse(any(l.startswith("|") for l in self.text.splitlines()))
        self.assertFalse(re.search("[\u2013\u2014\u2018\u2019\u201c\u201d]", self.text))
        self.assertFalse(any(l.startswith("#") and ":" in l for l in self.text.splitlines()))
        links = re.findall(r"\]\((file://[^)]+)\)", self.text)
        self.assertGreater(len(links), 10)
        for l in links:
            self.assertTrue(os.path.exists(urllib.parse.unquote(l[7:])), l)
        self.assertIn("### Recommendation 1 - ", self.text)
        self.assertIn("**G47 Micro vs macro separation:** fail", self.text)
        self.assertIn("#### Search | Widgets | AU", self.text)
    def test_executive_is_client_facing(self):
        self.assertNotIn("file://", self.exec)
        self.assertNotIn("draft", self.exec.split("What this does not measure")[0])
        self.assertIn("## The three changes that matter most", self.exec)
        self.assertIn("> **What this does not measure.**", self.exec)
        self.assertIn("## What we need from you", self.exec)
        self.assertIn("AUD 150.00 spent", self.exec)
    def test_json_carries_everything(self):
        j = json.loads((self.out / "audit.json").read_text())
        self.assertEqual(len(j["recommendations"]), len(self.rep.recs))
        self.assertIn("G47", j["controls"])
        self.assertTrue(any(m["source"].endswith("geo_90d.error.txt") for m in j["missing"]))

class CliTests(unittest.TestCase):
    def test_audit_subcommand(self):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            buf = StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.main(["audit", "--workspace", str(ws), "--run-date", RUN, "--executive"])
            self.assertEqual(rc, 0)
            self.assertIn("audit:", buf.getvalue())
            self.assertIn("draft recommendations", buf.getvalue())
            self.assertTrue((ws / "runs" / RUN / "audit-executive.md").exists())
    def test_no_workspace_is_one_clean_line(self):
        env = dict(os.environ); env.pop("GADS_WORKSPACE", None)
        from unittest import mock
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(StringIO()) as err:
            rc = cli.main(["audit"])
        self.assertEqual(rc, 2)
        self.assertIn("no workspace", err.getvalue())

if __name__ == "__main__":
    unittest.main()
