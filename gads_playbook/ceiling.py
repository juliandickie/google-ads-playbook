"""The 5-minute revenue-ceiling model from Keyword Planner volume (spec section 6.7)."""
import json
from pathlib import Path
from . import io, render
from .brand import Brand

COLS = {"keyword": ["Keyword", "Keyword text"], "volume": ["Avg. monthly searches", "Average monthly searches", "Searches"],
        "low": ["Top of page bid (low range)"], "high": ["Top of page bid (high range)"]}

def _col(row, names):
    for n in names:
        if n in row:
            return row[n]
    return ""

def _block(rows, ctr, cvr, aov, margin, cpc_override):
    volume = sum(io.parse_number(_col(r, COLS["volume"])) for r in rows)
    weighted = 0.0
    for r in rows:
        v = io.parse_number(_col(r, COLS["volume"]))
        low, high = io.parse_number(_col(r, COLS["low"])), io.parse_number(_col(r, COLS["high"]))
        mid = (low + high) / 2 if (low or high) else 0.0
        weighted += v * mid
    cpc = cpc_override if cpc_override is not None else ((weighted / volume) if volume else 0.0)
    clicks = volume * ctr
    purchases = clicks * cvr
    revenue = purchases * aov
    media = clicks * cpc
    profit = revenue * margin - media
    return {"volume": int(volume), "clicks": clicks, "purchases": purchases, "revenue": revenue, "cpc": cpc, "media_cost": media, "profit": profit,
            "keywords": [_col(r, COLS["keyword"]) for r in rows]}

def compute(rows, brand, aov, margin, brand_ctr=0.20, brand_cvr=0.10, nb_ctr=0.04, nb_cvr=0.02, brand_cpc=None, nb_cpc=None):
    if not rows or not any(n in rows[0] for n in COLS["keyword"]):
        raise io.MissingInput("Keyword Planner export needs a Keyword column and Avg. monthly searches.")
    b_rows = [r for r in rows if brand.is_branded(_col(r, COLS["keyword"]))]
    n_rows = [r for r in rows if r not in b_rows]
    b = _block(b_rows, brand_ctr, brand_cvr, aov, margin, brand_cpc)
    n = _block(n_rows, nb_ctr, nb_cvr, aov, margin, nb_cpc)
    total_rev, total_media = b["revenue"] + n["revenue"], b["media_cost"] + n["media_cost"]
    assumptions = [f"Brand block assumes {render.pct(brand_ctr)} CTR and {render.pct(brand_cvr)} CVR (practitioner defaults, not benchmarks).",
                   f"Non-brand block assumes {render.pct(nb_ctr)} CTR and {render.pct(nb_cvr)} CVR.",
                   "CPC is the volume-weighted midpoint of Keyword Planner top-of-page bids unless overridden." if brand_cpc is None and nb_cpc is None else "CPC overridden on the command line.",
                   f"AOV {aov:.2f}, gross margin {render.pct(margin)}. Volume is Keyword Planner monthly average for the chosen geo."]
    return {"brand": b, "nonbrand": n, "total": {"revenue": total_rev, "media_cost": total_media, "profit": b["profit"] + n["profit"],
                                                 "roas": (total_rev / total_media) if total_media else None}, "assumptions": assumptions}

def render_md(result, currency=""):
    def row(name, blk):
        return {"block": name, "volume": f"{blk['volume']:,}", "clicks": f"{blk['clicks']:,.0f}", "purchases": f"{blk['purchases']:,.0f}",
                "revenue": f"{currency} {blk['revenue']:,.0f}".strip(), "cpc": f"{blk['cpc']:.2f}", "media": f"{currency} {blk['media_cost']:,.0f}".strip(),
                "profit": f"{currency} {blk['profit']:,.0f}".strip()}
    t = result["total"]
    lines = ["# Revenue ceiling", "",
             render.table([row("Brand", result["brand"]), row("Non-brand", result["nonbrand"])],
                          ["block", "volume", "clicks", "purchases", "revenue", "cpc", "media", "profit"],
                          ["Block", "Monthly volume", "Clicks", "Purchases", "Revenue", "CPC", "Media cost", "Profit"]), "",
             f"Combined monthly revenue potential {currency} {t['revenue']:,.0f}, media cost {currency} {t['media_cost']:,.0f}, gross profit {currency} {t['profit']:,.0f}, blended ROAS {render.ratio(t['roas'])}.",
             "", "This is a ceiling, not a forecast. Replace the assumed rates with the account's own history as soon as it exists.", "",
             "## Assumptions", ""] + [f"- {a}" for a in result["assumptions"]] + ["", "## Keywords by block", "",
             "Brand: " + ", ".join(result["brand"]["keywords"]), "", "Non-brand: " + ", ".join(result["nonbrand"]["keywords"])]
    return "\n".join(lines) + "\n"

def cmd_ceiling(args):
    planner = Path(args.planner).expanduser()
    if not planner.exists():
        raise io.MissingInput(f"no Keyword Planner export at {planner}.")
    rows = io.read_csv(planner)
    tokens = [t.strip() for t in (args.brand or "").split(",") if t.strip()]
    if not tokens and args.workspace:
        from .cli import workspace_from
        tokens = io.load_workspace(workspace_from(args)).get("brand_tokens") or []
    if not tokens:
        raise io.MissingInput("no brand tokens. Pass --brand 'Name,Alt name' or a workspace with brand_tokens.")
    result = compute(rows, Brand(tokens), args.aov, args.margin, args.brand_ctr, args.brand_cvr, args.nonbrand_ctr, args.nonbrand_cvr, args.brand_cpc, args.nonbrand_cpc)
    md = render_md(result, args.currency)
    if args.workspace:
        from .cli import workspace_from
        out = io.run_dir(workspace_from(args), args.run_date)
        (out / "ceiling.md").write_text(md)
        (out / "ceiling.json").write_text(json.dumps(result, indent=2))
        print(f"ceiling: revenue {result['total']['revenue']:,.0f}, profit {result['total']['profit']:,.0f} -> {out / 'ceiling.md'}")
    else:
        print(md)
    return 0

def register(sub, add_common):
    p = sub.add_parser("ceiling", help="revenue-ceiling model from a Keyword Planner export")
    p.add_argument("planner", help="Keyword Planner CSV (utf-16 tab-separated downloads are fine)")
    p.add_argument("--aov", type=float, required=True)
    p.add_argument("--margin", type=float, required=True, help="gross margin as a fraction, e.g. 0.6")
    p.add_argument("--brand", help="comma-separated brand tokens; default from the workspace")
    p.add_argument("--currency", default="")
    p.add_argument("--brand-ctr", type=float, default=0.20)
    p.add_argument("--brand-cvr", type=float, default=0.10)
    p.add_argument("--nonbrand-ctr", type=float, default=0.04)
    p.add_argument("--nonbrand-cvr", type=float, default=0.02)
    p.add_argument("--brand-cpc", type=float)
    p.add_argument("--nonbrand-cpc", type=float)
    add_common(p)
    p.set_defaults(func=cmd_ceiling)
