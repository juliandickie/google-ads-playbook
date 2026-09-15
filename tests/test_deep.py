import argparse, contextlib, enum, json, re, tempfile, unittest
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock
from gads_playbook import deep, pull

class Approval(enum.IntEnum):
    """proto-plus enums are IntEnums: the JSON writer must name them, not number them."""
    APPROVED_LIMITED = 4

class Headline:
    """Stands in for a proto-plus message: has a class-level to_dict like proto.Message."""
    def __init__(self, text, pinned):
        self.text, self.pinned = text, pinned
    @classmethod
    def to_dict(cls, obj, use_integers_for_enums=True):
        return {"text": obj.text, "pinned_field": obj.pinned if use_integers_for_enums else "UNSPECIFIED"}

class FakeStream:
    def __init__(self, rows):
        self.results = rows

class FakeService:
    """Answers the customer time zone, one ad row, one conversion action row; empty for everything else.
    Fails on the resources named in fail_on, like the API rejecting a field."""
    def __init__(self, fail_on=()):
        self.calls = []
        self.fail_on = set(fail_on)
    def search_stream(self, customer_id, query):
        self.calls.append((customer_id, query))
        resource = query.split("FROM")[1].split()[0]
        if resource in self.fail_on:
            raise RuntimeError(f"Google Ads API Error: {resource} says no")
        if resource == "customer":
            return [FakeStream([NS(customer=NS(time_zone="Pacific/Auckland", id=1, descriptive_name="Example", currency_code="NZD",
                                               auto_tagging_enabled=True, optimization_score=0.5,
                                               conversion_tracking_setting=NS(conversion_tracking_status="X", enhanced_conversions_for_leads_enabled=True,
                                                                              google_ads_conversion_customer="customers/1", conversion_tracking_id=6)))])]
        if resource == "ad_group_ad":
            return [FakeStream([NS(campaign=NS(name="Search | Brand"), ad_group=NS(name="Core", status=NS(name="ENABLED")),
                                   ad_group_ad=NS(status=NS(name="ENABLED"),
                                                  ad=NS(id=7, type=NS(name="RESPONSIVE_SEARCH_AD"), final_urls=["https://example.com/a"],
                                                        responsive_search_ad=NS(headlines=[Headline("Buy now", 0)], descriptions=[])),
                                                  ad_strength=NS(name="GOOD"),
                                                  policy_summary=NS(approval_status=Approval.APPROVED_LIMITED, review_status=NS(name="REVIEWED"),
                                                                    policy_topic_entries=[Headline("CAPITALIZATION", 0)])))])]
        if resource == "conversion_action":
            return [FakeStream([NS(conversion_action=NS(id=99, name="Purchase", category=NS(name="PURCHASE"), status=NS(name="ENABLED"), primary_for_goal=True),
                                   metrics=NS(all_conversions=23.0, all_conversions_value=38545.0))])]
        return [FakeStream([])]

class FakeClient:
    def __init__(self, fail_on=()):
        self.svc = FakeService(fail_on)
    def get_service(self, name):
        return self.svc

END = date(2026, 9, 14)

class QueryShapeTests(unittest.TestCase):
    def test_every_query_renders_with_from_and_no_unresolved_placeholder(self):
        for name in deep.QUERIES:
            q = deep.render(name, END)
            self.assertIn("FROM", q, name)
            self.assertNotIn("{", q, f"{name} left a placeholder: {q}")
            self.assertNotIn("}", q, name)
            self.assertTrue(q.startswith("SELECT "), name)
    def test_windows_are_90_30_and_28_days_ending_yesterday_and_today(self):
        w = deep.windows(END)
        self.assertEqual(w["end"], "2026-09-14")
        self.assertEqual(w["m_start"], "2026-06-17")   # 90 days inclusive
        self.assertEqual(w["q_start"], "2026-08-16")   # 30 days inclusive
        self.assertEqual(w["c_end"], "2026-09-15")     # today, so this morning's change is visible
        self.assertEqual(w["c_start"], "2026-08-19")   # 28 days inclusive, inside the API's 30-day limit
        self.assertLess(date.fromisoformat(w["c_end"]) - date.fromisoformat(w["c_start"]), timedelta(days=30))
    def test_no_query_uses_during_last_90_days_or_selects_start_date(self):
        # GAQL gotchas met through the live API on 2026-09-05
        for name, q in deep.QUERIES.items():
            self.assertNotIn("LAST_90_DAYS", q, name)
            self.assertNotIn("campaign.start_date", q, name)
        self.assertNotIn("metrics.conversions,", deep.QUERIES["conversion_action_metrics_90d"])
        # a view filtered on campaign.status must select it (asset resources, geographic_view, landing_page_view
        # reject the query otherwise; every filtered query selects it so the rule has no exceptions to remember)
        for name, q in deep.QUERIES.items():
            if "campaign.status" in q.split("WHERE")[-1] and "WHERE" in q:
                self.assertIn("campaign.status", deep.select_fields(q), name)
        self.assertIn("LIMIT", deep.QUERIES["change_events_28d"])
        # campaign_criterion has no audience.audience field in v25 (ad_group_criterion does)
        self.assertNotIn("campaign_criterion.audience", deep.QUERIES["campaign_audiences"])
    def test_select_fields_parses_the_select_clause(self):
        self.assertEqual(deep.select_fields("SELECT a.b, c.d FROM x WHERE y"), ["a.b", "c.d"])
    def test_per_action_volumes_and_goal_categories_are_covered(self):
        q = deep.QUERIES
        self.assertIn("metrics.all_conversions", q["conversion_action_metrics_90d"])
        self.assertIn("segments.conversion_action_name", q["campaign_conversion_split_90d"])
        self.assertIn("customer_conversion_goal.biddable", q["customer_conversion_goals"])
        self.assertIn("campaign_conversion_goal.biddable", q["campaign_conversion_goals"])

class JsonValueTests(unittest.TestCase):
    def test_enums_are_named_not_numbered(self):
        self.assertEqual(deep.to_json(Approval.APPROVED_LIMITED), "APPROVED_LIMITED")
        self.assertEqual(deep.to_json(NS(name="ENABLED")), str(NS(name="ENABLED")))  # a namespace is not an enum
    def test_primitives_lists_dicts_and_messages(self):
        self.assertEqual(deep.to_json(4), 4)
        self.assertEqual(deep.to_json(True), True)
        self.assertEqual(deep.to_json(1.5), 1.5)
        self.assertEqual(deep.to_json(None), None)
        self.assertEqual(deep.to_json(["a", 2]), ["a", 2])
        self.assertEqual(deep.to_json({"k": Approval.APPROVED_LIMITED}), {"k": "APPROVED_LIMITED"})
        self.assertEqual(deep.to_json(Headline("x", 3)), {"text": "x", "pinned_field": "UNSPECIFIED"})
    def test_flatten_keeps_native_values_and_none_for_absent_paths(self):
        row = NS(campaign=NS(name="A", status=Approval.APPROVED_LIMITED), metrics=NS(clicks=3, conversions=1.5))
        out = deep.flatten(row, ["campaign.name", "campaign.status", "metrics.clicks", "metrics.conversions", "metrics.absent"])
        self.assertEqual(out, {"campaign.name": "A", "campaign.status": "APPROVED_LIMITED", "metrics.clicks": 3,
                               "metrics.conversions": 1.5, "metrics.absent": None})

class RunTests(unittest.TestCase):
    def test_writes_one_json_per_query_and_a_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeClient()
            m = deep.run("1234567890", d, run_date="2026-09-15", client=client)
            out = Path(d) / "raw" / "deep-2026-09-15"
            self.assertTrue((out / "manifest.json").exists())
            self.assertEqual(set(m["queries"]), set(deep.QUERIES))
            for name in deep.QUERIES:
                self.assertTrue((out / f"{name}.json").exists(), name)
                self.assertIsNone(m["queries"][name]["error"], name)
            ads = json.loads((out / "ads.json").read_text())
            self.assertEqual(len(ads), 1)
            self.assertEqual(ads[0]["ad_group_ad.policy_summary.approval_status"], "APPROVED_LIMITED")
            self.assertEqual(ads[0]["ad_group_ad.ad.final_urls"], ["https://example.com/a"])
            self.assertEqual(ads[0]["ad_group_ad.ad.responsive_search_ad.headlines"], [{"text": "Buy now", "pinned_field": "UNSPECIFIED"}])
            conv = json.loads((out / "conversion_action_metrics_90d.json").read_text())
            self.assertEqual(conv[0]["metrics.all_conversions"], 23.0)
            self.assertEqual(conv[0]["conversion_action.primary_for_goal"], True)
            self.assertEqual(m["windows"]["metrics"][1], m["window_end"])
            self.assertEqual(m["queries"]["ads"]["rows"], 1)
            # the time zone probe plus one call per query, every one against the same customer
            self.assertEqual(len(client.svc.calls), len(deep.QUERIES) + 1)
            self.assertTrue(all(c == "1234567890" for c, _ in client.svc.calls))
    def test_a_rejected_query_writes_error_txt_and_the_rest_still_write(self):
        with tempfile.TemporaryDirectory() as d:
            m = deep.run("1234567890", d, run_date="2026-09-15", client=FakeClient(fail_on={"geographic_view"}))
            out = Path(d) / "raw" / "deep-2026-09-15"
            self.assertFalse((out / "geo_90d.json").exists())
            err = (out / "geo_90d.error.txt").read_text()
            self.assertIn("geographic_view says no", err)
            self.assertIn("SELECT", err)
            self.assertEqual(m["queries"]["geo_90d"]["file"], "geo_90d.error.txt")
            self.assertIn("says no", m["queries"]["geo_90d"]["error"])
            self.assertTrue((out / "ads.json").exists())
            line, failed = deep.summary(m, d)
            self.assertEqual(failed, ["geo_90d"])
            self.assertIn(f"{len(deep.QUERIES)} queries", line)
            self.assertIn("1 failed (geo_90d)", line)
    def test_rerun_on_the_same_date_removes_the_earlier_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "raw" / "deep-2026-09-15"
            deep.run("1234567890", d, run_date="2026-09-15", client=FakeClient(fail_on={"geographic_view"}), names=["geo_90d"])
            self.assertTrue((out / "geo_90d.error.txt").exists())
            deep.run("1234567890", d, run_date="2026-09-15", client=FakeClient(), names=["geo_90d"])
            self.assertFalse((out / "geo_90d.error.txt").exists())
            self.assertTrue((out / "geo_90d.json").exists())
            deep.run("1234567890", d, run_date="2026-09-15", client=FakeClient(fail_on={"geographic_view"}), names=["geo_90d"])
            self.assertFalse((out / "geo_90d.json").exists())
            self.assertTrue((out / "geo_90d.error.txt").exists())
    def test_names_subset_runs_only_those(self):
        with tempfile.TemporaryDirectory() as d:
            m = deep.run("1234567890", d, run_date="2026-09-15", client=FakeClient(), names=["customer", "ads"])
            self.assertEqual(set(m["queries"]), {"customer", "ads"})
    def test_run_date_defaults_to_today(self):
        with tempfile.TemporaryDirectory() as d:
            m = deep.run("1234567890", d, client=FakeClient(), names=["customer"])
            self.assertEqual(m["run_date"], date.today().isoformat())
            self.assertTrue((Path(d) / "raw" / f"deep-{date.today().isoformat()}" / "customer.json").exists())

class CmdPullDeepTests(unittest.TestCase):
    def _args(self, **kw):
        base = dict(customer="1234567890", login_customer="9876543210", days=180, search_terms_days=None,
                    workspace=None, run_date="2026-09-15", deep=False, deep_only=False)
        base.update(kw)
        return argparse.Namespace(**base)
    def test_deep_runs_after_pull(self):
        calls = []
        def fake_pull(*a, **k):
            calls.append("pull"); return {"campaigns": 1}
        def fake_deep(customer_id, ws, run_date=None, client=None, names=None):
            calls.append(("deep", customer_id, run_date)); return {"run_date": run_date, "queries": {}}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pull, "run", side_effect=fake_pull), \
             mock.patch.object(deep, "run", side_effect=fake_deep), contextlib.redirect_stdout(StringIO()) as buf:
            rc = pull.cmd_pull(self._args(workspace=d, deep=True))
        self.assertEqual(rc, 0)
        self.assertEqual(calls, ["pull", ("deep", "1234567890", "2026-09-15")])
        self.assertIn("pull:", buf.getvalue())
        self.assertIn("deep:", buf.getvalue())
    def test_deep_only_skips_pull(self):
        calls = []
        def fake_deep(customer_id, ws, run_date=None, client=None, names=None):
            calls.append("deep"); return {"run_date": run_date, "queries": {"x": {"error": "boom", "file": "x.error.txt", "rows": None, "gaql": ""}}}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pull, "run", side_effect=AssertionError("pull must not run")), \
             mock.patch.object(deep, "run", side_effect=fake_deep), contextlib.redirect_stdout(StringIO()) as buf:
            rc = pull.cmd_pull(self._args(workspace=d, deep_only=True))
        self.assertEqual(calls, ["deep"])
        self.assertEqual(rc, 1)  # a failed query is reported loudly, not swallowed
        self.assertIn("1 failed (x)", buf.getvalue())
    def test_plain_pull_never_touches_deep(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pull, "run", return_value={"campaigns": 1}), \
             mock.patch.object(deep, "run", side_effect=AssertionError("deep must not run")), contextlib.redirect_stdout(StringIO()):
            self.assertEqual(pull.cmd_pull(self._args(workspace=d)), 0)
    def test_parser_has_both_flags_off_by_default(self):
        sub = argparse.ArgumentParser().add_subparsers()
        pull.register(sub, lambda p: p.add_argument("--workspace"))
        ns = sub.choices["pull"].parse_args(["--customer", "1", "--login-customer", "2"])
        self.assertFalse(ns.deep); self.assertFalse(ns.deep_only)
        ns = sub.choices["pull"].parse_args(["--customer", "1", "--login-customer", "2", "--deep-only"])
        self.assertTrue(ns.deep_only)

if __name__ == "__main__":
    unittest.main()
