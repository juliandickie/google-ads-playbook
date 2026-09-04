import argparse, contextlib, enum, json, os, sys, tempfile, types, unittest
from datetime import date, timedelta
from io import StringIO
from types import SimpleNamespace as NS
from pathlib import Path
from unittest import mock
from gads_playbook import pull, io

class Ch(enum.Enum):
    SEARCH = 2

class FakeStream:
    def __init__(self, rows):
        self.results = rows

class FakeService:
    def __init__(self, tz="Australia/Brisbane"):
        self.calls = []
        self.tz = tz
    def search_stream(self, customer_id, query):
        self.calls.append((customer_id, query))
        if "FROM customer" in query and "customer_client" not in query:
            return [FakeStream([NS(customer=NS(currency_code="AUD", time_zone=self.tz, descriptive_name="Example Co"))])]
        if "FROM campaign" in query:
            return [FakeStream([NS(segments=NS(date="2026-08-30"), campaign=NS(id=1, name="Search | Brand", status=NS(name="ENABLED"), advertising_channel_type=Ch.SEARCH, bidding_strategy_type=NS(name="TARGET_IMPRESSION_SHARE")),
                                   campaign_budget=NS(amount_micros=20000000), metrics=NS(impressions=1200, clicks=300, cost_micros=95400000, conversions=30.0, conversions_value=2700.0,
                                   search_impression_share=0.92, search_budget_lost_impression_share=0.05, search_rank_lost_impression_share=0.0))])]
        return [FakeStream([])]

class FakeClient:
    def __init__(self, tz="Australia/Brisbane"):
        self.svc = FakeService(tz)
    def get_service(self, name):
        return self.svc

class Ch2(enum.Enum):
    PERFORMANCE_MAX = 8

class PmaxFakeService(FakeService):
    """Same shape as FakeService, but the one campaign row is PMax with non-zero impression-share
    fields, so pull.run's channel-gated blanking (ruling R40) has something to blank."""
    def search_stream(self, customer_id, query):
        self.calls.append((customer_id, query))
        if "FROM customer" in query and "customer_client" not in query:
            return [FakeStream([NS(customer=NS(currency_code="AUD", time_zone=self.tz, descriptive_name="Example Co"))])]
        if "FROM campaign" in query:
            return [FakeStream([NS(segments=NS(date="2026-08-30"), campaign=NS(id=1, name="PMax | Scaling", status=NS(name="ENABLED"), advertising_channel_type=Ch2.PERFORMANCE_MAX, bidding_strategy_type=NS(name="MAXIMIZE_CONVERSION_VALUE")),
                                   campaign_budget=NS(amount_micros=20000000), metrics=NS(impressions=1200, clicks=300, cost_micros=95400000, conversions=30.0, conversions_value=2700.0,
                                   search_impression_share=0.0, search_budget_lost_impression_share=0.0, search_rank_lost_impression_share=0.0))])]
        return [FakeStream([])]

class PmaxFakeClient:
    def __init__(self, tz="Australia/Brisbane"):
        self.svc = PmaxFakeService(tz)
    def get_service(self, name):
        return self.svc

class PullTests(unittest.TestCase):
    def test_writes_canonical_files_and_gads_json(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            client = FakeClient()
            counts = pull.run("1234567890", "9876543210", 90, 180, ws, client=client)
            self.assertEqual(counts["campaigns"], 1)
            rows = io.read_csv(ws / "exports" / "campaigns.csv")
            self.assertEqual(rows[0]["campaign.advertising_channel_type"], "SEARCH")
            self.assertEqual(rows[0]["campaign.status"], "ENABLED")
            data = json.loads((ws / "gads.json").read_text())
            self.assertEqual(data["currency"], "AUD")
            self.assertEqual(data["customer_id"], "1234567890")
            self.assertIn("window_start", data)
            queried = {q.split("FROM")[1].split()[0] for _, q in client.svc.calls}
            self.assertTrue({"campaign", "search_term_view", "keyword_view", "shopping_performance_view", "conversion_action", "customer", "ad_group"} <= queried)
    def test_preserves_existing_brand_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            io.save_workspace(ws, {"brand_tokens": ["NordVital"], "target_roas": 4.0})
            pull.run("1234567890", "9876543210", 90, 180, ws, client=FakeClient())
            data = json.loads((ws / "gads.json").read_text())
            self.assertEqual(data["brand_tokens"], ["NordVital"])
            self.assertEqual(data["target_roas"], 4.0)

class RaisingService:
    """Fails on one named resource (matched from the query's FROM clause), otherwise behaves like FakeService for the customer query."""
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.calls = []
    def search_stream(self, customer_id, query):
        self.calls.append((customer_id, query))
        resource = query.split("FROM")[1].split()[0]
        if resource == self.fail_on:
            raise RuntimeError("Google says no")
        if resource == "customer":
            return [FakeStream([NS(customer=NS(currency_code="AUD", time_zone="Australia/Brisbane", descriptive_name="Example Co"))])]
        return [FakeStream([])]

class RaisingClient:
    def __init__(self, fail_on):
        self.svc = RaisingService(fail_on)
    def get_service(self, name):
        return self.svc

class PullApiFailureTests(unittest.TestCase):
    """Ruling R4 and R25: any API failure raises io.MissingInput naming the query and the two likely causes, and leaves the workspace with no exports/ and no gads.json."""
    def test_campaign_query_failure_raises_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            with self.assertRaises(io.MissingInput) as cm:
                pull.run("1234567890", "9876543210", 90, 180, ws, client=RaisingClient("campaign"))
            msg = str(cm.exception)
            self.assertIn("Google says no", msg)
            self.assertIn("campaign", msg)
            self.assertIn("developer token", msg)
            self.assertIn("login customer", msg)
            self.assertFalse((ws / "exports").exists())
            self.assertFalse((ws / "gads.json").exists())
    def test_customer_query_failure_raises_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            with self.assertRaises(io.MissingInput) as cm:
                pull.run("1234567890", "9876543210", 90, 180, ws, client=RaisingClient("customer"))
            msg = str(cm.exception)
            self.assertIn("Google says no", msg)
            self.assertIn("customer", msg)
            self.assertIn("developer token", msg)
            self.assertIn("login customer", msg)
            self.assertFalse((ws / "exports").exists())
            self.assertFalse((ws / "gads.json").exists())

class PullTimeZoneTests(unittest.TestCase):
    # R37: the window end is yesterday in the account's own time zone, not the runner's local date.
    def test_los_angeles_timezone_produces_iso_dates_and_no_window_note(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            pull.run("1234567890", "9876543210", 90, 180, ws, client=FakeClient(tz="America/Los_Angeles"))
            data = json.loads((ws / "gads.json").read_text())
            date.fromisoformat(data["window_end"])
            date.fromisoformat(data["window_start"])
            date.fromisoformat(data["search_terms_window_start"])
            self.assertNotIn("window_note", data)
    def test_unknown_timezone_falls_back_to_local_date_and_sets_window_note(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            pull.run("1234567890", "9876543210", 90, 180, ws, client=FakeClient(tz="Not/AZone"))
            data = json.loads((ws / "gads.json").read_text())
            self.assertEqual(data["window_end"], (date.today() - timedelta(days=1)).isoformat())
            self.assertEqual(data["window_note"], "account time zone unknown; window ended on the local date")
    def test_empty_timezone_falls_back_and_sets_window_note(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            pull.run("1234567890", "9876543210", 90, 180, ws, client=FakeClient(tz=""))
            data = json.loads((ws / "gads.json").read_text())
            self.assertEqual(data["window_note"], "account time zone unknown; window ended on the local date")

class PullImpressionShareTests(unittest.TestCase):
    # R40: search impression-share fields are meaningless off Search/Shopping and must be blanked, not
    # left as a stray 0.0 that reads as "eligible for every auction and winning none of them".
    def test_impression_share_blanked_for_non_search_channel(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            pull.run("1234567890", "9876543210", 90, 180, ws, client=PmaxFakeClient())
            rows = io.read_csv(ws / "exports" / "campaigns.csv")
            self.assertEqual(rows[0]["campaign.advertising_channel_type"], "PERFORMANCE_MAX")
            self.assertEqual(rows[0]["metrics.search_impression_share"], "")
            self.assertEqual(rows[0]["metrics.search_budget_lost_impression_share"], "")
            self.assertEqual(rows[0]["metrics.search_rank_lost_impression_share"], "")
    def test_impression_share_kept_for_search_channel(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            pull.run("1234567890", "9876543210", 90, 180, ws, client=FakeClient())
            rows = io.read_csv(ws / "exports" / "campaigns.csv")
            self.assertEqual(rows[0]["campaign.advertising_channel_type"], "SEARCH")
            self.assertEqual(rows[0]["metrics.search_impression_share"], "0.92")

class CmdPullWorkspaceTests(unittest.TestCase):
    # R38: cmd_pull's default workspace path (no --workspace, no GADS_WORKSPACE) strips dashes from the
    # customer id, matching auth's normalisation, so the two commands agree on one workspace path.
    def test_default_workspace_strips_dashes_from_customer_id(self):
        captured = {}
        def fake_run(customer_id, login_customer_id, days, search_terms_days, ws, client=None):
            captured["ws"] = ws
            return {}
        args = argparse.Namespace(customer="123-456-7890", login_customer="987-654-3210", days=90, search_terms_days=180,
                                  workspace=None, run_date=None)
        env = dict(os.environ)
        env.pop("GADS_WORKSPACE", None)
        with mock.patch.object(pull, "run", side_effect=fake_run), mock.patch.dict(os.environ, env, clear=True):
            with contextlib.redirect_stdout(StringIO()):
                pull.cmd_pull(args)
        self.assertEqual(captured["ws"], Path.home() / "gads" / "1234567890")

class MakeClientTests(unittest.TestCase):
    # R38: make_client wraps any exception from GoogleAdsClient.load_from_storage into io.MissingInput
    # naming the yaml path and quoting the error, instead of letting a raw client-library traceback escape.
    def test_load_storage_failure_wrapped_as_missing_input(self):
        fake_module = types.ModuleType("google.ads.googleads.client")
        class FakeGoogleAdsClient:
            @staticmethod
            def load_from_storage(path):
                raise RuntimeError("bad yaml")
        fake_module.GoogleAdsClient = FakeGoogleAdsClient
        with tempfile.TemporaryDirectory() as d:
            config_dir = Path(d)
            yaml = config_dir / "google-ads.yaml"
            yaml.write_text("developer_token: x\n")
            with mock.patch.object(pull, "CONFIG_DIR", config_dir), \
                 mock.patch.dict(sys.modules, {"google.ads.googleads.client": fake_module}):
                with self.assertRaises(io.MissingInput) as cm:
                    pull.make_client()
                self.assertIn(str(yaml), str(cm.exception))
                self.assertIn("bad yaml", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
