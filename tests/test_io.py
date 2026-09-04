import json, os, tempfile, unittest
from pathlib import Path
from gads_playbook import io

class MoneyTests(unittest.TestCase):
    def test_money_to_micros_handles_symbols_and_thousands(self):
        self.assertEqual(io.money_to_micros("$1,234.56"), 1234560000)
        self.assertEqual(io.money_to_micros("A$0.50"), 500000)
        self.assertEqual(io.money_to_micros("1234"), 1234000000)
    def test_money_to_micros_blank_and_dashes_are_none(self):
        self.assertIsNone(io.money_to_micros(""))
        self.assertIsNone(io.money_to_micros("--"))
        self.assertIsNone(io.money_to_micros(" -- "))
    def test_parse_percent(self):
        self.assertAlmostEqual(io.parse_percent("12.34%"), 0.1234)
        self.assertAlmostEqual(io.parse_percent("0.1234"), 0.1234)
        self.assertAlmostEqual(io.parse_percent("< 10%"), 0.10)
        self.assertIsNone(io.parse_percent("--"))
    def test_parse_number(self):
        self.assertEqual(io.parse_number("1,234"), 1234.0)
        self.assertEqual(io.parse_number(""), 0.0)
        self.assertEqual(io.parse_number("12.5"), 12.5)

class CsvTests(unittest.TestCase):
    def test_round_trip_and_utf16_tab(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.csv"
            io.write_csv(p, [{"a": "1", "b": "x"}], ["a", "b"])
            self.assertEqual(io.read_csv(p), [{"a": "1", "b": "x"}])
            q = Path(d) / "kp.csv"
            q.write_text("Keyword\tAvg. monthly searches\nmagnesium\t1,000\n", encoding="utf-16")
            self.assertEqual(io.read_csv(q), [{"Keyword": "magnesium", "Avg. monthly searches": "1,000"}])
    def test_read_csv_lines_sniffs_delimiter_from_in_memory_lines(self):
        lines = ["Keyword\tAvg. monthly searches", "magnesium\t1,000"]
        self.assertEqual(io.read_csv_lines(lines), [{"Keyword": "magnesium", "Avg. monthly searches": "1,000"}])
        lines = ["a,b", "1,x"]
        self.assertEqual(io.read_csv_lines(lines), [{"a": "1", "b": "x"}])
    def test_require_names_missing_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.csv"
            io.write_csv(p, [{"campaign.name": "x"}], ["campaign.name"])
            with self.assertRaises(io.MissingInput) as cm:
                io.require(p, ["campaign.name", "metrics.cost_micros"])
            self.assertIn("metrics.cost_micros", str(cm.exception))
            self.assertIn("c.csv", str(cm.exception))
    def test_require_names_missing_file(self):
        with self.assertRaises(io.MissingInput) as cm:
            io.require(Path("/nonexistent/exports/campaigns.csv"), ["campaign.name"])
        self.assertIn("campaigns.csv", str(cm.exception))
    def test_require_header_only_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "campaigns.csv"
            io.write_csv(p, [], ["campaign.name"])
            with self.assertRaises(io.MissingInput) as cm:
                io.require(p, ["campaign.name", "metrics.cost_micros"])
            self.assertIn("metrics.cost_micros", str(cm.exception))
    def test_require_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "campaigns.csv"
            p.write_bytes(b"")
            with self.assertRaises(io.MissingInput) as cm:
                io.require(p, ["campaign.name"])
            self.assertIn("campaigns.csv", str(cm.exception))
    def test_require_header_only_all_columns_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "search_terms.csv"
            io.write_csv(p, [], ["campaign.name", "metrics.cost_micros"])
            self.assertEqual(io.require(p, ["campaign.name", "metrics.cost_micros"]), [])

class WorkspaceTests(unittest.TestCase):
    def test_load_save_and_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            with self.assertRaises(io.MissingInput):
                io.load_workspace(ws)
            io.save_workspace(ws, {"customer_id": "1234567890", "currency": "AUD"})
            self.assertEqual(io.load_workspace(ws)["currency"], "AUD")
            r = io.run_dir(ws, "2026-09-04")
            self.assertTrue(r.is_dir())
            self.assertEqual(r.name, "2026-09-04")

if __name__ == "__main__":
    unittest.main()
