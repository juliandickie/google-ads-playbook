import json, shutil, tempfile, unittest
from pathlib import Path
from gads_playbook import windows, io, schema, cli

WS = Path(__file__).parent / "fixtures" / "ws60"

def _new_campaign_rows(start_day, end_day, name="Search | NonBrand | BOF | New"):
    rows = []
    for day in range(start_day, end_day + 1):
        rows.append({"segments.date": f"2026-08-{day:02d}", "campaign.id": "4", "campaign.name": name, "campaign.status": "ENABLED",
                     "campaign.advertising_channel_type": "SEARCH", "campaign.bidding_strategy_type": "MAXIMIZE_CONVERSIONS", "campaign_budget.amount_micros": "100000000",
                     "metrics.impressions": "1000", "metrics.clicks": "50", "metrics.cost_micros": "100000000", "metrics.conversions": "5.0", "metrics.conversions_value": "600.00",
                     "metrics.search_impression_share": "0.5", "metrics.search_budget_lost_impression_share": "0.0", "metrics.search_rank_lost_impression_share": "0.3"})
    return rows

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.c = io.read_csv(WS / "exports" / "campaigns.csv")
    def test_verdicts(self):
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        by = {c["campaign"]: c for c in r["campaigns"]}
        self.assertEqual(by["Search | NonBrand | BOF | Winner"]["verdict"], "scale")
        self.assertTrue(by["Search | NonBrand | BOF | Winner"]["budget_limited"])
        noisy = by["Search | NonBrand | BOF | Noisy"]
        self.assertEqual(noisy["verdict"], "hold")
        self.assertGreater(noisy["windows"][7]["cur"]["roas"], 4.0)
        self.assertLess(noisy["windows"][30]["cur"]["roas"], 4.0)
        self.assertTrue(any("30" in s for s in noisy["reasons"]))
        self.assertEqual(by["Search | NonBrand | TOF | Loser"]["verdict"], "cut")
    def test_window_arithmetic(self):
        r = windows.compute(self.c, target_roas=4.0)
        w = {c["campaign"]: c for c in r["campaigns"]}["Search | NonBrand | BOF | Winner"]["windows"][7]
        self.assertEqual(w["cur"]["cost"], 700_000_000)
        self.assertAlmostEqual(w["cur"]["conversions"], 35.0)
        self.assertAlmostEqual(w["cur"]["cpa"], 20.0)
        self.assertEqual(r["end_date"], "2026-08-31")
        self.assertEqual(r["unavailable"], [])
    def test_short_history_marks_unavailable(self):
        short = [x for x in self.c if x["segments.date"] >= "2026-08-12"]  # 20 days
        r = windows.compute(short, target_roas=4.0)
        self.assertEqual(r["unavailable"], [14, 30])
        self.assertIn(7, r["campaigns"][0]["windows"])
    def test_render(self):
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        md = windows.render_md(r, "AUD")
        self.assertIn("scale", md)
        self.assertIn("7 days", md)
    def test_account_rollup_rendered(self):
        # R19: render_md must render an account section built from result["account"]["windows"],
        # with no verdict line, using the same Window/Cost/Conv/ROAS/Prior ROAS/Delta/CPA table shape.
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        self.assertEqual(r["account"]["windows"][7]["cur"]["cost"], 2_100_000_000)  # three campaigns at 700 each
        md = windows.render_md(r, "AUD")
        self.assertIn("## Account", md)
        self.assertIn("AUD 2,100.00", md)
        account_section = md.split("## Account", 1)[1]
        self.assertNotIn("Verdict:", account_section)
    def test_availability_is_per_campaign(self):
        # R20: each campaign's available window lengths come from that campaign's own earliest
        # segments.date, not the global earliest date. A campaign with 14 days of its own history
        # (2026-08-18 to 2026-08-31) gets the 7-day window (needs 2*7=14 total days) but not the
        # 14-day or 30-day windows (need 28 and 60 total days respectively) -- the same
        # (end - first).days + 1 >= 2 * L rule already used for the global "unavailable" list,
        # just evaluated against this campaign's own rows instead of the account's earliest date.
        new_rows = _new_campaign_rows(18, 31)
        self.assertEqual(len(new_rows), 14)
        rows = self.c + new_rows
        r = windows.compute(rows, target_roas=4.0, breakeven_roas=2.5)
        by = {c["campaign"]: c for c in r["campaigns"]}
        new = by["Search | NonBrand | BOF | New"]
        self.assertEqual(list(new["windows"].keys()), [7])
        self.assertEqual(new["unavailable"], [14, 30])
        self.assertEqual(new["verdict"], "hold")
        self.assertTrue(any("not all windows available" in s for s in new["reasons"]))
        winner = by["Search | NonBrand | BOF | Winner"]
        self.assertEqual(sorted(winner["windows"].keys()), [7, 14, 30])
        self.assertEqual(winner["verdict"], "scale")
        self.assertEqual(winner["unavailable"], [])
        self.assertEqual(r["unavailable"], [])  # global/account availability is unaffected
        md = windows.render_md(r, "AUD")
        self.assertIn("Windows unavailable for this campaign (not enough history): 14 days, 30 days.", md)
    def test_rank_lost_7d_averages_last_seven_days(self):
        # R30: windows surfaces the 7-day rank-lost impression share average per campaign,
        # since the gads-manage diagnostic cites it and windows.md previously had no such value.
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        by = {c["campaign"]: c for c in r["campaigns"]}
        self.assertAlmostEqual(by["Search | NonBrand | BOF | Winner"]["rank_lost_7d"], 0.1)
        self.assertAlmostEqual(by["Search | NonBrand | TOF | Loser"]["rank_lost_7d"], 0.5)
    def test_rank_lost_rendered(self):
        r = windows.compute(self.c, target_roas=4.0, breakeven_roas=2.5)
        md = windows.render_md(r, "AUD")
        self.assertIn("Rank lost impression share (7 days): 10.0%", md)
    def test_rank_lost_empty_cells_render_na(self):
        rows = _new_campaign_rows(18, 31)
        for row in rows:
            row["metrics.search_rank_lost_impression_share"] = ""
        r = windows.compute(self.c + rows, target_roas=4.0, breakeven_roas=2.5)
        by = {c["campaign"]: c for c in r["campaigns"]}
        new = by["Search | NonBrand | BOF | New"]
        self.assertIsNone(new["rank_lost_7d"])
        md = windows.render_md(r, "AUD")
        section = md.split("## Search | NonBrand | BOF | New", 1)[1]
        self.assertIn("Rank lost impression share (7 days): n/a", section)
    def test_cmd_missing_budget_lost_column_exits_2(self):
        # R21: metrics.search_budget_lost_impression_share is a required column for `gads windows`,
        # even though empty cell values within it are fine.
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "ws"
            shutil.copytree(WS, ws)
            rows = io.read_csv(ws / "exports" / "campaigns.csv")
            cols = [c for c in schema.COLUMNS["campaigns"] if c != "metrics.search_budget_lost_impression_share"]
            io.write_csv(ws / "exports" / "campaigns.csv", rows, cols)
            self.assertEqual(cli.main(["windows", "--workspace", str(ws), "--run-date", "2026-09-04"]), 2)

if __name__ == "__main__":
    unittest.main()
