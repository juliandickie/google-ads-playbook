"""The 7, 14, 30-day scaling gate (spec section 6.6). A signal must hold in all three windows."""
import json
from collections import defaultdict
from datetime import date, timedelta
from . import io, render

LENGTHS = (7, 14, 30)

def _num(v):
    return float(v) if (v or "") != "" else 0.0

def _agg(rows):
    cost = sum(int(_num(r.get("metrics.cost_micros"))) for r in rows)
    conv = sum(_num(r.get("metrics.conversions")) for r in rows)
    value = sum(_num(r.get("metrics.conversions_value")) for r in rows)
    money = io.micros_to_money(cost)
    return {"cost": cost, "conversions": conv, "value": value,
            "roas": (value / money) if money else None, "cpa": (money / conv) if conv else None, "days": len({r["segments.date"] for r in rows})}

def _window(rows, end, length):
    cur_start = end - timedelta(days=length - 1)
    prior_start = cur_start - timedelta(days=length)
    cur = [r for r in rows if cur_start.isoformat() <= r["segments.date"] <= end.isoformat()]
    prior = [r for r in rows if prior_start.isoformat() <= r["segments.date"] < cur_start.isoformat()]
    c, p = _agg(cur), _agg(prior)
    delta = None
    if c["roas"] is not None and p["roas"]:
        delta = (c["roas"] - p["roas"]) / p["roas"]
    return {"cur": c, "prior": p, "delta_roas": delta}

def _verdict(wins, target, breakeven, tolerance, min_conversions):
    reasons = []
    ok = True
    zero_spend = []
    for L, w in wins.items():
        if w["cur"]["cost"] == 0:
            ok = False
            zero_spend.append(L)
            reasons.append(f"no spend in the {L}-day window")
            continue
        roas = w["cur"]["roas"]
        if roas is None or roas < target:
            ok = False
            reasons.append(f"{L}-day ROAS {render.ratio(roas)} is under target {render.ratio(target)}")
        if w["delta_roas"] is not None and w["delta_roas"] < -tolerance:
            ok = False
            reasons.append(f"{L}-day ROAS down {render.pct(-w['delta_roas'])} versus the prior {L} days")
    if ok and len(wins) == len(LENGTHS):
        return "scale", ["ROAS at or above target in all three windows and no window down more than " + render.pct(tolerance)]
    if breakeven is not None and len(wins) == len(LENGTHS) and not zero_spend:
        below = all((w["cur"]["roas"] or 0) < breakeven for w in wins.values())
        conv30 = wins[30]["cur"]["conversions"]
        if below and conv30 >= min_conversions:
            return "cut", [f"ROAS under break-even {render.ratio(breakeven)} in all three windows with {conv30:.0f} conversions over 30 days"]
    if len(wins) < len(LENGTHS):
        reasons.append("not all windows available; no scale decision until 60 days of history exist")
    return "hold", reasons or ["mixed signals"]

def compute(campaigns, target_roas, breakeven_roas=None, end_date=None, tolerance=0.10, min_conversions=5, budget_limited=0.10):
    if not campaigns:
        raise io.MissingInput("campaigns.csv has no rows.")
    dates = sorted({r["segments.date"] for r in campaigns if r.get("segments.date")})
    if not dates:
        raise io.MissingInput("campaigns.csv has no segments.date column values; windows needs daily rows (gads pull, or a UI export with the Day column).")
    end = date.fromisoformat(end_date or dates[-1])
    first = date.fromisoformat(dates[0])
    available = [L for L in LENGTHS if (end - first).days + 1 >= 2 * L]
    unavailable = [L for L in LENGTHS if L not in available]
    by = defaultdict(list)
    for r in campaigns:
        by[r["campaign.name"]].append(r)
    out = []
    for name, rows in by.items():
        camp_dates = sorted({r["segments.date"] for r in rows if r.get("segments.date")})
        if not camp_dates:
            raise io.MissingInput(f"campaign '{name}' has no segments.date values in campaigns.csv; windows needs daily rows for every campaign.")
        camp_first = date.fromisoformat(camp_dates[0])
        camp_available = [L for L in LENGTHS if (end - camp_first).days + 1 >= 2 * L]
        camp_unavailable = [L for L in LENGTHS if L not in camp_available]
        wins = {L: _window(rows, end, L) for L in camp_available}
        verdict, reasons = _verdict(wins, target_roas, breakeven_roas, tolerance, min_conversions)
        last7 = [r for r in rows if (end - timedelta(days=6)).isoformat() <= r["segments.date"] <= end.isoformat()]
        bl_vals = [io.parse_percent(r.get("metrics.search_budget_lost_impression_share")) for r in last7]
        bl_vals = [v for v in bl_vals if v is not None]
        bl = bool(bl_vals) and (sum(bl_vals) / len(bl_vals)) > budget_limited
        rl_vals = [io.parse_percent(r.get("metrics.search_rank_lost_impression_share")) for r in last7]
        rl_vals = [v for v in rl_vals if v is not None]
        rank_lost_7d = (sum(rl_vals) / len(rl_vals)) if rl_vals else None
        step = {"scale": "raise budget 20 percent, re-read in 72 hours", "cut": "pause or cut budget by half and rework structure before re-testing", "hold": "no budget change"}[verdict]
        if verdict == "scale" and not bl:
            step += " (not budget-limited: check rank-lost impression share before adding budget)"
        out.append({"campaign": name, "windows": wins, "verdict": verdict, "reasons": reasons, "budget_limited": bl, "rank_lost_7d": rank_lost_7d, "step": step, "unavailable": camp_unavailable})
    acct = {L: _window(campaigns, end, L) for L in available}
    return {"end_date": end.isoformat(), "campaigns": out, "account": {"windows": acct}, "unavailable": unavailable,
            "target_roas": target_roas, "breakeven_roas": breakeven_roas, "tolerance": tolerance}

_WIN_COLS = ["w", "cost", "conv", "roas", "prior", "delta", "cpa"]
_WIN_HEADS = ["Window", "Cost", "Conv", "ROAS", "Prior ROAS", "Delta", "CPA"]

def _window_table_rows(windows, currency):
    rows = []
    for L, w in windows.items():
        rows.append({"w": f"{L} days", "cost": render.money(w["cur"]["cost"], currency), "conv": f"{w['cur']['conversions']:.1f}",
                     "roas": render.ratio(w["cur"]["roas"]), "prior": render.ratio(w["prior"]["roas"]), "delta": render.pct(w["delta_roas"]) if w["delta_roas"] is not None else "n/a",
                     "cpa": f"{w['cur']['cpa']:.2f}" if w["cur"]["cpa"] else "n/a"})
    return rows

def render_md(result, currency=""):
    lines = [f"# Scaling gate, ending {result['end_date']}", "",
             f"Target ROAS {render.ratio(result['target_roas'])}. Break-even {render.ratio(result['breakeven_roas'])}. Scale only when all three windows agree."]
    if result["unavailable"]:
        lines.append(f"Windows unavailable (not enough history): {', '.join(str(x) + ' days' for x in result['unavailable'])}.")
    for c in result["campaigns"]:
        lines += ["", f"## {c['campaign']} - {c['verdict'].upper()}", ""]
        lines.append(render.table(_window_table_rows(c["windows"], currency), _WIN_COLS, _WIN_HEADS))
        if c.get("unavailable"):
            lines.append(f"Windows unavailable for this campaign (not enough history): {', '.join(str(x) + ' days' for x in c['unavailable'])}.")
        lines += ["", f"Verdict: {c['verdict']}", "Reasons: " + "; ".join(c["reasons"]), f"Budget limited: {'yes' if c['budget_limited'] else 'no'}", f"Rank lost impression share (7 days): {render.pct(c['rank_lost_7d'])}", f"Step: {c['step']}"]
    lines += ["", "## Account", ""]
    lines.append(render.table(_window_table_rows(result["account"]["windows"], currency), _WIN_COLS, _WIN_HEADS))
    return "\n".join(lines) + "\n"

def cmd_windows(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    data = io.load_workspace(ws)
    camps = io.require(ws / "exports" / "campaigns.csv", ["segments.date", "campaign.name", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value", "metrics.search_budget_lost_impression_share", "metrics.search_rank_lost_impression_share"])
    target = args.target_roas or data.get("target_roas")
    if not target:
        raise io.MissingInput("no target ROAS. Pass --target-roas or set target_roas in gads.json (gads setup).")
    result = compute(camps, float(target), args.breakeven_roas or data.get("breakeven_roas"), args.end_date, args.tolerance, args.min_conversions, args.budget_limited)
    out = io.run_dir(ws, args.run_date)
    (out / "windows.md").write_text(render_md(result, data.get("currency", "")))
    (out / "windows.json").write_text(json.dumps(result, indent=2))
    counts = {}
    for c in result["campaigns"]:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    print("windows: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + f" -> {out / 'windows.md'}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("windows", help="7, 14, 30-day scaling gate per campaign")
    p.add_argument("--target-roas", type=float)
    p.add_argument("--breakeven-roas", type=float)
    p.add_argument("--end-date", help="YYYY-MM-DD, default latest date in campaigns.csv")
    p.add_argument("--tolerance", type=float, default=0.10)
    p.add_argument("--min-conversions", type=float, default=5)
    p.add_argument("--budget-limited", type=float, default=0.10)
    add_common(p)
    p.set_defaults(func=cmd_windows)
