import enum, json, tempfile, unittest
from types import SimpleNamespace as NS
from pathlib import Path
from gads_playbook import pull, io

class Ch(enum.Enum):
    SEARCH = 2

class FakeStream:
    def __init__(self, rows):
        self.results = rows

class FakeService:
    def __init__(self):
        self.calls = []
    def search_stream(self, customer_id, query):
        self.calls.append((customer_id, query))
        if "FROM customer" in query and "customer_client" not in query:
            return [FakeStream([NS(customer=NS(currency_code="AUD", time_zone="Australia/Brisbane", descriptive_name="Example Co"))])]
        if "FROM campaign" in query:
            return [FakeStream([NS(segments=NS(date="2026-08-30"), campaign=NS(id=1, name="Search | Brand", status=NS(name="ENABLED"), advertising_channel_type=Ch.SEARCH, bidding_strategy_type=NS(name="TARGET_IMPRESSION_SHARE")),
                                   campaign_budget=NS(amount_micros=20000000), metrics=NS(impressions=1200, clicks=300, cost_micros=95400000, conversions=30.0, conversions_value=2700.0,
                                   search_impression_share=0.92, search_budget_lost_impression_share=0.05, search_rank_lost_impression_share=0.0))])]
        return [FakeStream([])]

class FakeClient:
    def __init__(self):
        self.svc = FakeService()
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
