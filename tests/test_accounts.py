import enum, unittest
from types import SimpleNamespace as NS
from gads_playbook import accounts, io

class Status(enum.Enum):
    ENABLED = 2

class FakeStream:
    def __init__(self, rows):
        self.results = rows

class FakeAccountsService:
    def search_stream(self, customer_id, query):
        row = NS(customer_client=NS(id=1112223333, descriptive_name="Client A", manager=False, level=1, currency_code="AUD", status=Status.ENABLED))
        return [FakeStream([row])]

class FakeAccountsClient:
    def __init__(self):
        self.svc = FakeAccountsService()
    def get_service(self, name):
        return self.svc

class AccountsTests(unittest.TestCase):
    def test_lists_client_accounts(self):
        rows = accounts.run("9876543210", client=FakeAccountsClient())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "1112223333")
        self.assertEqual(rows[0]["name"], "Client A")
        self.assertEqual(rows[0]["manager"], "")
        self.assertEqual(rows[0]["status"], "ENABLED")
    def test_query_selects_level_but_does_not_filter_on_it(self):
        # R39: the level <= 1 filter hid sub-manager accounts and their clients; level is still
        # selected (and printed) so the operator can see the depth, but nothing is excluded by it.
        self.assertIn("customer_client.level", accounts.QUERY)
        self.assertNotIn("WHERE", accounts.QUERY)

class RaisingAccountsService:
    def search_stream(self, customer_id, query):
        raise RuntimeError("Google says no")

class RaisingAccountsClient:
    def __init__(self):
        self.svc = RaisingAccountsService()
    def get_service(self, name):
        return self.svc

class AccountsApiFailureTests(unittest.TestCase):
    """Ruling R4: an API failure on the customer_client query raises io.MissingInput naming that resource."""
    def test_customer_client_query_failure_raises_missing_input(self):
        with self.assertRaises(io.MissingInput) as cm:
            accounts.run("9876543210", client=RaisingAccountsClient())
        msg = str(cm.exception)
        self.assertIn("Google says no", msg)
        self.assertIn("customer_client", msg)
