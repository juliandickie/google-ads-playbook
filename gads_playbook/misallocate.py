"""Spend misallocation: search terms converting well but underfunded, and the reverse (spec section 6.4)."""
import json
from collections import defaultdict
from . import io, render

def _num(v):
    return float(v) if (v or "") != "" else 0.0

def compute(terms, campaigns, min_conversions=5, win_cvr=0.20, win_share=0.02, lose_cvr=0.03, lose_share=0.05):
    camp_term_cost = defaultdict(int)
    for r in terms:
        camp_term_cost[r["campaign.name"]] += int(_num(r.get("metrics.cost_micros")))
    winners, losers = [], []
    for r in terms:
        conv = _num(r.get("metrics.conversions"))
        if conv < min_conversions:
            continue
        clicks = _num(r.get("metrics.clicks"))
        cost = int(_num(r.get("metrics.cost_micros")))
        ccost = camp_term_cost[r["campaign.name"]] or 1
        cvr = conv / clicks if clicks else 0.0
        share = cost / ccost
        row = {"term": r["search_term_view.search_term"], "campaign": r["campaign.name"], "ad_group": r.get("ad_group.name", ""),
               "match_type": r.get("segments.search_term_match_type", ""), "clicks": int(clicks), "conversions": conv, "cvr": cvr,
               "cost": cost, "campaign_cost": ccost, "share": share, "value": _num(r.get("metrics.conversions_value"))}
        if cvr > win_cvr and share < win_share:
            winners.append(row)
        elif cvr < lose_cvr and share > lose_share:
            losers.append(row)
    winners.sort(key=lambda x: -x["conversions"])
    losers.sort(key=lambda x: -x["cost"])
    reallocation = []
    for w in winners:
        reallocation.append({"term": w["term"], "campaign": w["campaign"],
                             "proposal": f"Move '{w['term']}' into a dedicated ad group (exact match) with its own budget; it converts at {render.pct(w['cvr'])} on {render.pct(w['share'])} of campaign spend."})
    for l in losers:
        reallocation.append({"term": l["term"], "campaign": l["campaign"],
                             "proposal": f"Review '{l['term']}' ({render.pct(l['cvr'])} CVR on {render.pct(l['share'])} of spend): add as a negative to this campaign, or move it to a TOF test campaign with a capped budget if the intent is real."})
    return {"winners": winners, "losers": losers, "reallocation": reallocation,
            "thresholds": {"min_conversions": min_conversions, "win_cvr": win_cvr, "win_share": win_share, "lose_cvr": lose_cvr, "lose_share": lose_share}}

def _rows(items, currency):
    return [{"term": i["term"], "campaign": i["campaign"], "clicks": i["clicks"], "conv": f"{i['conversions']:.1f}", "cvr": render.pct(i["cvr"]),
             "cost": render.money(i["cost"], currency), "share": render.pct(i["share"]), "value": f"{i['value']:,.0f}"} for i in items]

def render_md(result, currency=""):
    t = result["thresholds"]
    cols = ["term", "campaign", "clicks", "conv", "cvr", "cost", "share", "value"]
    heads = ["Search term", "Campaign", "Clicks", "Conv", "CVR", "Cost", "Share of campaign", "Conv value"]
    lines = ["# Spend misallocation audit", "",
             f"Terms with at least {t['min_conversions']} conversions. Winners: CVR above {render.pct(t['win_cvr'])} on under {render.pct(t['win_share'])} of campaign spend. Losers: CVR under {render.pct(t['lose_cvr'])} on over {render.pct(t['lose_share'])} of campaign spend.",
             "", "## Underfunded winners", ""]
    lines.append(render.table(_rows(result["winners"], currency), cols, heads) if result["winners"] else "None found.")
    lines += ["", "## Overfunded losers", ""]
    lines.append(render.table(_rows(result["losers"], currency), cols, heads) if result["losers"] else "None found.")
    lines += ["", "## Reallocation plan", ""]
    lines += [f"- {r['proposal']}" for r in result["reallocation"]] or ["- Nothing to move."]
    return "\n".join(lines) + "\n"

def cmd_misallocate(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    data = io.load_workspace(ws)
    terms = io.require(ws / "exports" / "search_terms.csv", ["search_term_view.search_term", "campaign.name", "metrics.clicks", "metrics.cost_micros", "metrics.conversions"])
    camps = io.require(ws / "exports" / "campaigns.csv", ["campaign.name", "metrics.cost_micros"])
    result = compute(terms, camps, args.min_conversions, args.win_cvr, args.win_share, args.lose_cvr, args.lose_share)
    out = io.run_dir(ws, args.run_date)
    (out / "misallocation.md").write_text(render_md(result, data.get("currency", "")))
    (out / "misallocation.json").write_text(json.dumps(result, indent=2))
    print(f"misallocate: {len(result['winners'])} underfunded winners, {len(result['losers'])} overfunded losers -> {out / 'misallocation.md'}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("misallocate", help="search terms converting well but underfunded, and the reverse")
    p.add_argument("--min-conversions", type=float, default=5)
    p.add_argument("--win-cvr", type=float, default=0.20)
    p.add_argument("--win-share", type=float, default=0.02)
    p.add_argument("--lose-cvr", type=float, default=0.03)
    p.add_argument("--lose-share", type=float, default=0.05)
    add_common(p)
    p.set_defaults(func=cmd_misallocate)
