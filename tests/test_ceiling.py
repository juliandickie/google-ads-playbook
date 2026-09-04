import contextlib
import io as iomod
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from gads_playbook import ceiling, io, cli
from gads_playbook.brand import Brand

KP = Path(__file__).parent / "fixtures" / "keyword_planner.csv"
WS = Path(__file__).parent / "fixtures" / "ws"

class CeilingTests(unittest.TestCase):
    def setUp(self):
        self.rows = io.read_csv(KP)
        self.b = Brand(["NordVital"])
    def test_blocks(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        self.assertEqual(r["brand"]["volume"], 7000)
        self.assertEqual(r["nonbrand"]["volume"], 90000)
        self.assertAlmostEqual(r["brand"]["clicks"], 1400)
        self.assertAlmostEqual(r["brand"]["purchases"], 140)
        self.assertAlmostEqual(r["brand"]["revenue"], 140 * 88)
        self.assertAlmostEqual(r["nonbrand"]["clicks"], 3600)
        self.assertAlmostEqual(r["nonbrand"]["purchases"], 72)
    def test_cpc_midpoint_and_overrides(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        # brand cpc = volume-weighted midpoint: (5000*0.40 + 2000*0.55) / 7000
        self.assertAlmostEqual(r["brand"]["cpc"], (5000 * 0.40 + 2000 * 0.55) / 7000, places=4)
        r2 = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6, brand_cpc=0.10, nb_cpc=1.50)
        self.assertAlmostEqual(r2["brand"]["media_cost"], 1400 * 0.10)
        self.assertAlmostEqual(r2["nonbrand"]["media_cost"], 3600 * 1.50)
        self.assertAlmostEqual(r2["brand"]["profit"], 140 * 88 * 0.6 - 140)
    def test_assumptions_listed_and_render(self):
        r = ceiling.compute(self.rows, self.b, aov=88.0, margin=0.6)
        self.assertTrue(any("20" in a and "CTR" in a for a in r["assumptions"]))
        md = ceiling.render_md(r, "AUD")
        self.assertIn("ceiling, not a forecast", md)

class ColumnValidationTests(unittest.TestCase):
    def setUp(self):
        self.b = Brand(["NordVital"])
    def test_missing_volume_column_raises(self):
        rows = [{"Keyword": "nordvital", "Volume renamed": "7000",
                 "Top of page bid (low range)": "0.40", "Top of page bid (high range)": "0.60"}]
        with self.assertRaisesRegex(io.MissingInput, "volume"):
            ceiling.compute(rows, self.b, aov=88.0, margin=0.6)
    def test_missing_bid_columns_without_override_raises(self):
        rows = [{"Keyword": "nordvital", "Avg. monthly searches": "7000"}]
        with self.assertRaisesRegex(io.MissingInput, "--brand-cpc"):
            ceiling.compute(rows, self.b, aov=88.0, margin=0.6)
    def test_missing_bid_columns_with_both_overrides_computes(self):
        rows = [{"Keyword": "nordvital", "Avg. monthly searches": "7000"}]
        r = ceiling.compute(rows, self.b, aov=88.0, margin=0.6, brand_cpc=0.5, nb_cpc=2.0)
        self.assertAlmostEqual(r["brand"]["media_cost"], 1400 * 0.5)
    def test_single_bid_value_used_as_midpoint(self):
        rows = [{"Keyword": "widget", "Avg. monthly searches": "1000", "Top of page bid (low range)": "1.00"}]
        blk = ceiling._block(rows, ctr=0.20, cvr=0.10, aov=88.0, margin=0.6, cpc_override=None)
        self.assertAlmostEqual(blk["cpc"], 1.00)

class WorkspaceResolutionTests(unittest.TestCase):
    def test_gads_workspace_env_var_used_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws_path = Path(tmp) / "ws"
            shutil.copytree(WS, ws_path)
            with mock.patch.dict(os.environ, {"GADS_WORKSPACE": str(ws_path)}):
                buf = iomod.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = cli.main(["ceiling", str(KP), "--aov", "88", "--margin", "0.6", "--currency", "AUD", "--run-date", "2026-09-04"])
            self.assertEqual(rc, 0)
            md_path = ws_path / "runs" / "2026-09-04" / "ceiling.md"
            self.assertTrue(md_path.exists())
            self.assertIn("Brand: nordvital", md_path.read_text())
    def test_no_workspace_prints_markdown_and_writes_nothing(self):
        with mock.patch.dict(os.environ, {"GADS_WORKSPACE": ""}):
            buf = iomod.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.main(["ceiling", str(KP), "--aov", "88", "--margin", "0.6", "--brand", "NordVital"])
        self.assertEqual(rc, 0)
        self.assertIn("Brand: nordvital", buf.getvalue())

if __name__ == "__main__":
    unittest.main()
