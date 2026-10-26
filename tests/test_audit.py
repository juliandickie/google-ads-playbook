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

REVIEW = """# Reviewed additions

## Recommendation - Competitor names decided

**Section:** misallocation

**After:** A fortnightly negative pass

**Campaign:** all enabled

**Issue:** competitor names bought without a decision; see recommendation {rec:"Generic negatives} for the list mechanics.

**Evidence:** search_terms.csv

**Rule:** 06 G14

**Confidence:** medium

**Change:** negatives for the names that never convert.

**Risk:** low.

**Impact:** cleaner data.

**Rollback:** remove.

**Window:** 30 days.

## Recommendation - A landing page call

**Section:** roles

**Campaign:** Search | Widgets | AU

**Issue:** the homepage takes spend.

**Change:** point the ad group at the widgets page.

## Override - Search Partners on one campaign

**Drop:** yes

## Override - Rebuild the Poor-strength ads

**Confidence:** medium

**Risk:** the client writes its own ads; two weeks of their time.

## Campaign - Search | Widgets | AU

**Job:** non-brand acquisition, widgets, Australia.

**Decision metric:** new-customer ROAS.

**Overlap:** shares Australia with the NZ campaign (recommendation {rec:One auction per market}).

## Campaign - No Such Campaign

**Job:** nothing.

## Caveat

**Reviewed 2026-09-22:** two recommendations added by hand, one dropped; see {rec:Competitor names}.
"""

class EnhancedConversionsTests(unittest.TestCase):
    """v26 replaced the leads-only flag with the account-wide effective setting; the audit reads either."""
    def run_with(self, customer):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            (ws / "raw" / f"deep-{DEEP}" / "customer.json").write_text(json.dumps([customer]))
            rep, out = audit.run(ws, RUN)
            return rep, (out / "audit.md").read_text()
    def test_effective_on_is_partial(self):
        rep, text = self.run_with({"customer.auto_tagging_enabled": True,
                                   "customer.conversion_tracking_setting.enablement_setting": None,
                                   "customer.conversion_tracking_setting.effective_enablement_setting": "ON",
                                   "customer.conversion_tracking_setting.conversion_tracking_status": "CONVERSION_TRACKING_MANAGED_BY_SELF"})
        self.assertEqual(rep.controls["G43"][0], "partial")
        self.assertIn("enhanced conversions on (effective setting)", text)
        self.assertNotIn("for leads", text)
    def test_effective_off_is_a_warning(self):
        rep, text = self.run_with({"customer.auto_tagging_enabled": True,
                                   "customer.conversion_tracking_setting.effective_enablement_setting": "OFF"})
        self.assertEqual(rep.controls["G43"][0], "warning")
        self.assertIn("enhanced conversions off (effective setting)", text)
    def test_legacy_flag_still_reads_for_older_deep_passes(self):
        rep, text = self.run_with({"customer.auto_tagging_enabled": True,
                                   "customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled": True})
        self.assertEqual(rep.controls["G43"][0], "partial")
        self.assertIn("enhanced conversions for leads on", text)

class ApiVersionLineTests(unittest.TestCase):
    def test_manifest_version_is_printed_and_absent_when_unrecorded(self):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            _, out = audit.run(ws, RUN)
            self.assertNotIn("**Google Ads API:**", (out / "audit.md").read_text())
            mp = ws / "raw" / f"deep-{DEEP}" / "manifest.json"
            m = json.loads(mp.read_text()); m.update({"api_version": "v26", "client_version": "34.0.0"}); mp.write_text(json.dumps(m))
            _, out = audit.run(ws, RUN)
            self.assertIn("**Google Ads API:** v26, client google-ads 34.0.0.", (out / "audit.md").read_text())

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = full_ws(self.tmp.name)
        (self.ws / "runs" / RUN / "audit-review.md").write_text(REVIEW)
        self.rep, self.out = audit.run(self.ws, RUN, executive=True)
        self.text = (self.out / "audit.md").read_text()
    def tearDown(self):
        self.tmp.cleanup()
    def test_added_recommendation_sits_after_its_anchor_and_is_numbered(self):
        titles = rec_titles(self.rep)
        i = titles.index("A fortnightly negative pass")
        self.assertEqual(titles[i + 1], "Competitor names decided")
        self.assertEqual([r["number"] for r in self.rep.recs], list(range(1, len(self.rep.recs) + 1)))
        added = next(r for r in self.rep.recs if r["title"] == "Competitor names decided")
        self.assertEqual(added["reviewed"], "added")
        self.assertEqual(added["Owner"], audit.OWNER)          # defaults filled
        self.assertEqual(added["Approval"], audit.DRAFT)
        self.assertIn("**Reviewed:** added by the reviewer in audit-review.md.", self.text)
    def test_added_without_anchor_goes_to_its_section_end(self):
        titles = rec_titles(self.rep)
        roles = [r["title"] for r in self.rep.recs if r["section"] == "roles"]
        self.assertEqual(roles[-1], "A landing page call")
    def test_override_drops_and_edits(self):
        titles = rec_titles(self.rep)
        self.assertNotIn("Search Partners on one campaign", titles)
        poor = next(r for r in self.rep.recs if r["title"] == "Rebuild the Poor-strength ads")
        self.assertEqual(poor["Confidence"], "medium")
        self.assertIn("two weeks", poor["Risk"])
        self.assertEqual(poor["reviewed"], "edited")
        self.assertIn("dropped the draft", " ".join(self.rep.review_notes))
    def test_tokens_resolve_to_numbers(self):
        self.assertNotIn("{rec:", self.text)
        added = next(r for r in self.rep.recs if r["title"] == "Competitor names decided")
        generic = next(r for r in self.rep.recs if r["title"].startswith('"Generic negatives"'))
        self.assertIn(f"recommendation {generic['number']} for the list", added["Issue"])
        overlap = next(r for r in self.rep.recs if r["title"].startswith("One auction per market"))
        self.assertIn(f"(recommendation {overlap['number']})", self.text)
        self.assertIn(f"see {added['number']}.", self.text)
    def test_campaign_lines_merge_in_order_and_unknown_campaign_is_reported(self):
        block = next(lines for n, lines in self.rep.campaigns if n == "Search | Widgets | AU")
        labels = [l for l, _ in block]
        self.assertEqual(labels[0], "Job")
        self.assertLess(labels.index("Signal"), labels.index("Decision metric"))
        self.assertLess(labels.index("Decision metric"), labels.index("Overlap"))
        self.assertTrue(any("No Such Campaign" in n for n in self.rep.review_notes))
        self.assertIn("Could not place:", self.text)
    def test_caveat_and_json(self):
        self.assertIn("**Reviewed 2026-09-22:** two recommendations added", self.text)
        self.assertIn("2 recommendations added and 1 edited", self.text)
        j = json.loads((self.out / "audit.json").read_text())
        self.assertEqual(j["review"]["file"], f"runs/{RUN}/audit-review.md")
        self.assertEqual(sum(1 for r in j["recommendations"] if r.get("reviewed") == "added"), 2)
    def test_rerun_is_idempotent(self):
        first = self.text
        audit.run(self.ws, RUN, executive=True)
        self.assertEqual((self.out / "audit.md").read_text(), first)
    def test_executive_can_pick_a_reviewed_recommendation(self):
        three = audit.three_changes(self.rep)
        self.assertEqual(len(three), 3)

class FiveMistakesTests(unittest.TestCase):
    def run_ws(self, change=None):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            if change:
                change(ws)
            rep, out = audit.run(ws, RUN, executive=True)
            return rep, (out / "audit.md").read_text(), json.loads((out / "audit.json").read_text())
    def verdicts(self, rep):
        return {m: v for m, v, _ in rep.mistakes}
    def test_each_mistake_is_answered_from_the_files(self):
        rep, text, j = self.run_ws()
        v = self.verdicts(rep)
        self.assertEqual(v["No branded campaign"], "not needed today")       # the earlier SERP check says no bid, no brand campaign
        self.assertEqual(v["Sending traffic to the homepage"], "yes")        # 10 of 100 landing-page spend on the homepage
        self.assertEqual(v["Letting PMax run wild"], "no")                   # no PMax campaign
        self.assertEqual(v["Scaling before you have data"], "no")            # no budget change events
        self.assertEqual(v["Ignoring your product feed"], "not applicable")
        self.assertIn("## The five mistakes these prompts keep finding", text)
        self.assertIn("**1. No branded campaign:** not needed today (no protect verdict among the 1 phrase checked on 2026-09-05, so the brand ranks first", text)
        self.assertLess(text.index("## The five mistakes"), text.index("## The three changes"))
        self.assertEqual([m["mistake"] for m in j["mistakes"]], [m for m, _, _ in rep.mistakes])
    def test_landing_pages_absent_or_empty(self):
        rep, _, _ = self.run_ws(lambda ws: (ws / "raw" / f"deep-{DEEP}" / "landing_pages_90d.json").write_text("[]"))
        self.assertEqual(self.verdicts(rep)["Sending traffic to the homepage"], "no")
        rep, _, _ = self.run_ws(lambda ws: (ws / "raw" / f"deep-{DEEP}" / "landing_pages_90d.json").unlink())
        self.assertEqual(self.verdicts(rep)["Sending traffic to the homepage"], "no evidence")
    def test_protect_verdict_without_a_brand_campaign_is_the_mistake(self):
        def protect(ws):
            (ws / "runs" / "2026-09-05" / "brand-serp.md").write_text("| phrase | country | rank | paid | verdict |\n|---|---|---|---|---|\n| example co | AU | 3 | rival.com | protect |\n| example co | NZ | 1 | none | no bid |\n")
        rep, text, _ = self.run_ws(protect)
        self.assertEqual(self.verdicts(rep)["No branded campaign"], "yes")
        self.assertIn("1 of the 2 phrases checked on 2026-09-05 has a protect verdict and no brand campaign covers it", text)
    def test_budget_changes_with_nothing_cleared_by_the_gate(self):
        def budget(ws):
            p = ws / "raw" / f"deep-{DEEP}" / "change_events_28d.json"
            p.write_text(json.dumps([{"change_event.change_resource_type": "CAMPAIGN_BUDGET", "change_event.user_email": "x@example.com", "change_event.change_date_time": "2026-09-10 10:00:00"}]))
            w = ws / "runs" / RUN / "windows.json"
            d = json.loads(w.read_text())
            for c in d["campaigns"]:
                c["verdict"] = "hold"
            w.write_text(json.dumps(d))
        rep, _, _ = self.run_ws(budget)
        self.assertEqual(self.verdicts(rep)["Scaling before you have data"], "yes")
    def test_capture_only_pmax_and_an_unscored_feed(self):
        def pmax(ws):
            rows = audit.io.read_csv(ws / "exports" / "campaigns.csv")
            rows.append(camp_row("PMax | Capture | AU", "2026-09-01", 20_000_000, 2, 100.0, channel="PERFORMANCE_MAX", strategy="MAXIMIZE_CONVERSION_VALUE", cid=3))
            write_csv(ws / "exports" / "campaigns.csv", rows, CAMP_COLS)
            lj = ws / "runs" / RUN / "leakage.json"
            d = json.loads(lj.read_text())
            d["per_campaign"].append({"campaign": "PMax | Capture | AU", "kind": "pmax-capture", "cost": 20_000_000, "value": 100.0, "branded_cost": 20_000_000, "branded_value": 100.0, "nonbranded_cost": 0, "nonbranded_value": 0.0})
            lj.write_text(json.dumps(d))
            (ws / "feed.tsv").write_text("id\ttitle\n")
        rep, _, _ = self.run_ws(pmax)
        v = self.verdicts(rep)
        self.assertEqual(v["Letting PMax run wild"], "yes")
        self.assertEqual(v["Ignoring your product feed"], "no evidence")   # feed present, feedscore not run
        def scored(ws):
            pmax(ws)
            (ws / "runs" / RUN / "feedscore.json").write_text(json.dumps({"rebuild": ["A", "B"], "scored": 5}))
        rep, text, _ = self.run_ws(scored)
        self.assertEqual(self.verdicts(rep)["Ignoring your product feed"], "yes")
        self.assertIn("2 of 5 products score under 7", text)

class WordingTests(unittest.TestCase):
    def test_counts_agree_and_no_brackets_nest_or_lines_trail(self):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            (ws / "raw" / f"deep-{DEEP}" / "customer.json").write_text(json.dumps([{"customer.auto_tagging_enabled": True, "customer.conversion_tracking_setting.effective_enablement_setting": "ON"}]))
            rep, out = audit.run(ws, RUN, executive=True)
            text = (out / "audit.md").read_text()
        self.assertIn("Branded searches reach 1 non-brand campaign: ", text)
        self.assertIn("(1 large list missing from some campaigns)", text)
        self.assertIn("(1 negative list; the checklist expects themed", text)
        self.assertIn("(1 keyword at 3 or below)", text)
        self.assertIn("(1 campaign pair competes in the same auctions)", text)
        self.assertIn("(0 changes in 28 days)", text)
        self.assertIn("**Impact:** about AUD 5.00 per window back", text)   # the executive quotes this Impact line when the rec is in its top three
        self.assertEqual(audit.count(1, "keyword"), "1 keyword")
        for line in text.splitlines():
            self.assertEqual(line, line.rstrip(), line)
            if line.startswith("**G"):   # control notes sit in one pair of brackets, never two
                depth = deepest = 0
                for ch in line:
                    depth += (ch == "(") - (ch == ")"); deepest = max(deepest, depth)
                self.assertLessEqual(deepest, 1, line)

class FollowUpTests(unittest.TestCase):
    def test_a_later_readout_is_linked_and_a_same_day_one_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            (ws / "runs" / RUN / "readout.md").write_text("# Readout against the earlier audit\n")
            (ws / "runs" / "provisional-2026-12-01").mkdir()
            (ws / "runs" / "provisional-2026-12-01" / "readout.md").write_text("# not a dated run\n")
            _, out = audit.run(ws, RUN)
            self.assertNotIn("**Follow-up:**", (out / "audit.md").read_text())
            (ws / "runs" / "2026-10-15").mkdir()
            (ws / "runs" / "2026-10-15" / "readout.md").write_text("# Readout against the 2026-09-15 audit\n")
            _, out = audit.run(ws, RUN)
            text = (out / "audit.md").read_text()
            self.assertIn("**Follow-up:** the readout of 2026-10-15, [readout.md](file://", text)
            self.assertIn("runs/2026-10-15/readout.md", text)

class ShortPullTests(unittest.TestCase):
    def test_a_missing_30_day_window_reads_not_available(self):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            w = ws / "runs" / RUN / "windows.json"
            data = json.loads(w.read_text())
            data["account"]["windows"] = {"7": {"cur": {"cost": 10_000_000, "conversions": 1, "value": 10.0, "roas": 1.0, "cpa": 10.0}}}
            data["unavailable"] = [14, 30]
            w.write_text(json.dumps(data))
            rep, out = audit.run(ws, RUN, executive=True)
            text = (out / "audit.md").read_text()
            self.assertIn("**Last 30 days:** not available, windows.md lists the 30-day window as unavailable", text)
            self.assertNotIn("cost 0.00, 0.0 conversions", text)
            self.assertNotIn("The last 30 days", (out / "audit-executive.md").read_text())

class ValueCoverageTests(unittest.TestCase):
    def run_with(self, account):
        with tempfile.TemporaryDirectory() as d:
            ws = full_ws(d)
            lj = ws / "runs" / RUN / "leakage.json"
            data = json.loads(lj.read_text()); data["account"].update(account); lj.write_text(json.dumps(data))
            _, out = audit.run(ws, RUN, executive=True)
            return (out / "audit.md").read_text(), (out / "audit-executive.md").read_text()
    def test_under_the_floor_reads_n_a_in_both_reports(self):
        text, exe = self.run_with({"true_new_customer_roas": None, "term_value_coverage": 0.0, "term_value_coverage_floor": 0.25})
        self.assertIn("**True new-customer ROAS (branded terms stripped out of every campaign):** n/a (under the value coverage floor)", text)
        self.assertIn("**Search-term value coverage:** 0.0 percent", text)
        self.assertIn("**New-customer return:** not measurable from this window, because search terms show only 0.0 percent", exe)
        self.assertNotIn("0.00x once branded", exe)
    def test_above_the_floor_states_the_coverage(self):
        text, exe = self.run_with({"term_value_coverage": 0.4, "term_value_coverage_floor": 0.25})
        self.assertIn("**Search-term value coverage:** 40.0 percent", text)
        self.assertIn("read on the 40 percent of tracked value that search terms show", exe)
    def test_leakage_json_from_before_the_coverage_reads_as_before(self):
        text, exe = self.run_with({})
        self.assertNotIn("Search-term value coverage", text)
        self.assertNotIn("of tracked value that search terms show", exe)

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
