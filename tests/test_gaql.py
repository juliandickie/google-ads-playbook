import enum, pathlib, unittest
from types import SimpleNamespace as NS
from gads_playbook import gaql, schema

class Status(enum.Enum):
    ENABLED = 2

class GaqlTests(unittest.TestCase):
    def test_every_canonical_file_has_a_query_selecting_its_columns(self):
        for name, cols in schema.COLUMNS.items():
            q = gaql.render(name, "2026-06-03", "2026-08-31")
            for c in cols:
                self.assertIn(c, q, f"{name} query lacks {c}")
            self.assertIn("FROM", q)
        self.assertIn("segments.date BETWEEN '2026-06-03' AND '2026-08-31'", gaql.render("campaigns", "2026-06-03", "2026-08-31"))
        self.assertNotIn("segments.date,", gaql.render("keywords", "2026-06-03", "2026-08-31").split("FROM")[0])
        self.assertNotIn("BETWEEN", gaql.render("conversion_actions", "2026-06-03", "2026-08-31"))
        self.assertIn("customer.currency_code", gaql.render("customer", "", ""))
    def test_flatten_walks_paths_and_names_enums(self):
        row = NS(campaign=NS(name="A", status=Status.ENABLED, id=12), metrics=NS(cost_micros=95400000, conversions=30.0),
                 segments=NS(date="2026-08-30"), campaign_budget=NS(amount_micros=20000000))
        out = gaql.flatten(row, ["segments.date", "campaign.id", "campaign.name", "campaign.status", "metrics.cost_micros", "metrics.conversions", "campaign_budget.amount_micros", "metrics.search_impression_share"])
        self.assertEqual(out["campaign.status"], "ENABLED")
        self.assertEqual(out["campaign.id"], "12")
        self.assertEqual(out["metrics.cost_micros"], "95400000")
        self.assertEqual(out["metrics.conversions"], "30.0")
        self.assertEqual(out["metrics.search_impression_share"], "")

class UvTests(unittest.TestCase):
    def test_uv_command_shape(self):
        from gads_playbook.cli import uv_command
        cmd, root = uv_command(["pull", "--customer", "1"])
        self.assertEqual(cmd[:4], ["uv", "run", "--python", "3.12"])
        self.assertIn("google-ads>=25", cmd)
        self.assertEqual(cmd[-3:], ["pull", "--customer", "1"])
        # the root is the checkout, whatever the folder is called (clones and the plugin cache use other names)
        self.assertTrue((pathlib.Path(root) / "gads_playbook" / "cli.py").is_file(), root)
        self.assertTrue((pathlib.Path(root) / "bin" / "gads").is_file(), root)
