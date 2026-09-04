import unittest
from gads_playbook import render

class RenderTests(unittest.TestCase):
    def test_table_escapes_pipes_and_orders_columns(self):
        out = render.table([{"a": "x|y", "b": 2}], ["a", "b"], headers=["A", "B"])
        self.assertEqual(out.splitlines()[0], "| A | B |")
        self.assertEqual(out.splitlines()[1], "|---|---|")
        self.assertIn("x\\|y", out)
    def test_money_and_pct(self):
        self.assertEqual(render.money(1234560000, "AUD"), "AUD 1,234.56")
        self.assertEqual(render.pct(0.1234), "12.3%")
        self.assertEqual(render.pct(None), "n/a")

if __name__ == "__main__":
    unittest.main()
