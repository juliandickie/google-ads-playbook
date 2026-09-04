"""Branded leakage audit and true new-customer ROAS (spec section 6.3)."""
import json
from collections import defaultdict
from . import io, render
from .brand import Brand

def _num(v):
    return float(v) if (v or "") != "" else 0.0

def _int(v):
    return int(float(v)) if (v or "") != "" else 0

SEARCH_LIKE_CHANNELS = ("SEARCH", "SHOPPING", "")
SEARCH_KINDS = ("brand", "nonbrand")
TRUE_ROAS_EXCLUDED_KINDS = ("pmax-unknown", "other-channel", "terms-only")

def compute(campaigns, terms, brand, keywords=None, flag_share=0.20, windows=None):
    windows = windows or {}
    campaign_start, campaign_end = windows.get("window_start") or "", windows.get("window_end") or ""
    search_terms_start = windows.get("search_terms_window_start") or ""
    campaign_window = f"{campaign_start} to {campaign_end}" if campaign_start and campaign_end else ""
    search_terms_window = f"{search_terms_start} to {campaign_end}" if search_terms_start and campaign_end else ""
    windows_differ = bool(search_terms_start) and search_terms_start != campaign_start
    assumptions = []
    if windows_differ:
        assumptions.append(
            f"Search terms cover {search_terms_start} to {campaign_end} while campaigns cover {campaign_start} to {campaign_end}; "
            "branded share and true new-customer ROAS mix the two windows and over-state leakage. "
            "Re-run gads pull with --search-terms-days equal to --days for a window-consistent read."
        )
    kinds, channel = {}, {}
    for r in campaigns:
        name = r["campaign.name"]
        channel[name] = r.get("campaign.advertising_channel_type", "")
    for name, ch in channel.items():
        chu = (ch or "").upper()
        if chu == "PERFORMANCE_MAX" or chu in SEARCH_LIKE_CHANNELS:
            kinds[name] = brand.classify_campaign(name, ch, keywords)
        else:
            kinds[name] = "other-channel"
    totals = defaultdict(lambda: {"cost": 0, "conversions": 0.0, "value": 0.0})
    for r in campaigns:
        t = totals[r["campaign.name"]]
        t["cost"] += _int(r.get("metrics.cost_micros"))
        t["conversions"] += _num(r.get("metrics.conversions"))
        t["value"] += _num(r.get("metrics.conversions_value"))
    split = defaultdict(lambda: {"branded_cost": 0, "branded_value": 0.0, "branded_conv": 0.0,
                                 "nonbranded_cost": 0, "nonbranded_value": 0.0, "nonbranded_conv": 0.0})
    for r in terms:
        name = r["campaign.name"]
        if name not in totals:
            totals[name]  # campaign present in terms only; keep zero totals
            kinds[name] = "terms-only"
        side = "branded" if brand.is_branded(r["search_term_view.search_term"]) else "nonbranded"
        s = split[name]
        s[side + "_cost"] += _int(r.get("metrics.cost_micros"))
        s[side + "_value"] += _num(r.get("metrics.conversions_value"))
        s[side + "_conv"] += _num(r.get("metrics.conversions"))
    per = []
    for name, t in totals.items():
        kind = kinds.get(name, "nonbrand")
        if kind == "other-channel":
            per.append({"campaign": name, "kind": kind, "cost": t["cost"], "conversions": t["conversions"], "value": t["value"],
                        "branded_cost": 0, "branded_value": 0.0, "nonbranded_cost": 0, "nonbranded_value": 0.0, "other_cost": 0})
            continue
        if kind == "terms-only":
            s = split[name]
            cost = s["branded_cost"] + s["nonbranded_cost"]
            value = s["branded_value"] + s["nonbranded_value"]
            conv = s["branded_conv"] + s["nonbranded_conv"]
            per.append({"campaign": name, "kind": kind, "cost": cost, "conversions": conv, "value": value,
                        "branded_cost": s["branded_cost"], "branded_value": s["branded_value"],
                        "nonbranded_cost": s["nonbranded_cost"], "nonbranded_value": s["nonbranded_value"], "other_cost": 0})
            continue
        s = split[name]
        if kind.startswith("pmax"):
            if kind == "pmax-scaling":
                s = {"branded_cost": 0, "branded_value": 0.0, "branded_conv": 0.0,
                     "nonbranded_cost": t["cost"], "nonbranded_value": t["value"], "nonbranded_conv": t["conversions"]}
                assumptions.append(f"PMax campaign '{name}' counted whole as non-branded (scaling campaign by name tag; no search terms available).")
            elif kind == "pmax-capture":
                s = {"branded_cost": t["cost"], "branded_value": t["value"], "branded_conv": t["conversions"],
                     "nonbranded_cost": 0, "nonbranded_value": 0.0, "nonbranded_conv": 0.0}
                assumptions.append(f"PMax campaign '{name}' counted whole as branded (capture campaign by name tag).")
            else:
                assumptions.append(f"PMax campaign '{name}' could not be classified from its name; excluded from the true new-customer ROAS. Tag it Capture or Scaling, or supply a PMax search terms insight export.")
        other = None if windows_differ else max(t["cost"] - s["branded_cost"] - s["nonbranded_cost"], 0)
        per.append({"campaign": name, "kind": kind, "cost": t["cost"], "conversions": t["conversions"], "value": t["value"],
                    "branded_cost": s["branded_cost"], "branded_value": s["branded_value"],
                    "nonbranded_cost": s["nonbranded_cost"], "nonbranded_value": s["nonbranded_value"], "other_cost": other})
    other_channel_names = sorted(name for name, k in kinds.items() if k == "other-channel")
    if other_channel_names:
        assumptions.append(f"Non-search campaigns ({', '.join(other_channel_names)}) are shown separately; search terms cannot classify them.")
    terms_only_names = sorted(name for name, k in kinds.items() if k == "terms-only")
    if terms_only_names:
        assumptions.append(f"{', '.join(terms_only_names)} appear in search terms but not in campaigns.csv (outside the campaign window or removed); excluded from the account totals.")
    total_cost = sum(p["cost"] for p in per if p["kind"] != "terms-only")
    total_value = sum(p["value"] for p in per if p["kind"] != "terms-only")
    nb_camps = [p for p in per if p["kind"] in ("nonbrand", "pmax-scaling")]
    nb_cost = sum(p["cost"] for p in nb_camps)
    nb_value = sum(p["value"] for p in nb_camps)
    nb_branded_value = sum(p["branded_value"] for p in nb_camps)
    true_cost = sum(p["nonbranded_cost"] for p in per if p["kind"] not in TRUE_ROAS_EXCLUDED_KINDS)
    true_value = sum(p["nonbranded_value"] for p in per if p["kind"] not in TRUE_ROAS_EXCLUDED_KINDS)
    reverse = [p for p in per if p["kind"] == "brand"]
    account = {
        "total_cost": total_cost, "total_value": total_value,
        "blended_roas": (total_value / io.micros_to_money(total_cost)) if total_cost else None,
        "reported_nonbrand_cost": nb_cost, "reported_nonbrand_value": nb_value,
        "reported_nonbrand_roas": (nb_value / io.micros_to_money(nb_cost)) if nb_cost else None,
        "branded_share_of_nonbrand_value": (nb_branded_value / nb_value) if nb_value else None,
        "true_new_customer_cost": true_cost, "true_new_customer_value": true_value,
        "true_new_customer_roas": (true_value / io.micros_to_money(true_cost)) if true_cost else None,
        "reverse_leak_cost": sum(p["nonbranded_cost"] for p in reverse),
        "reverse_leak_value": sum(p["nonbranded_value"] for p in reverse),
        "flag": bool(nb_value and (nb_branded_value / nb_value) > flag_share),
        "flag_share": flag_share,
        "campaign_window": campaign_window,
        "search_terms_window": search_terms_window,
    }
    if not windows_differ:
        other_total = sum(p["other_cost"] for p in per if p["kind"] in SEARCH_KINDS)
        if other_total:
            assumptions.append(f"{render.money(other_total)} of search campaign cost has no search term row (Google's privacy threshold hides low-volume terms). Leakage is a floor.")
    return {"per_campaign": per, "account": account, "assumptions": assumptions}

def render_md(result, currency=""):
    a = result["account"]
    rows = []
    other_rows = []
    for p in result["per_campaign"]:
        if p["kind"] == "other-channel":
            other_rows.append({"campaign": p["campaign"], "cost": render.money(p["cost"], currency),
                               "conversions": f"{p['conversions']:.1f}", "value": f"{p['value']:,.0f}"})
            continue
        other_display = "n/a (windows differ)" if p["other_cost"] is None else render.money(p["other_cost"], currency)
        rows.append({"campaign": p["campaign"], "kind": p["kind"], "cost": render.money(p["cost"], currency),
                     "branded_value": f"{p['branded_value']:,.0f}", "nonbranded_value": f"{p['nonbranded_value']:,.0f}",
                     "branded_cost": render.money(p["branded_cost"], currency), "nonbranded_cost": render.money(p["nonbranded_cost"], currency),
                     "other": other_display})
    lines = ["# Branded leakage audit", ""]
    window_parts = []
    if a.get("campaign_window"):
        window_parts.append(f"Campaign window {a['campaign_window']}.")
    if a.get("search_terms_window"):
        window_parts.append(f"Search terms window {a['search_terms_window']}.")
    if window_parts:
        lines += [" ".join(window_parts), ""]
    lines.append(render.table(rows, ["campaign", "kind", "cost", "branded_cost", "branded_value", "nonbranded_cost", "nonbranded_value", "other"],
                              ["Campaign", "Kind", "Cost", "Branded cost", "Branded value", "Non-branded cost", "Non-branded value", "Unattributed cost"]))
    if other_rows:
        lines += ["", "## Other channels", "",
                  render.table(other_rows, ["campaign", "cost", "conversions", "value"], ["Campaign", "Cost", "Conversions", "Value"])]
    lines += ["", "## Before and after", "",
              render.table([
                  {"m": "Blended ROAS (all campaigns)", "v": render.ratio(a["blended_roas"])},
                  {"m": "Reported non-brand ROAS (non-brand campaigns as reported)", "v": render.ratio(a["reported_nonbrand_roas"])},
                  {"m": "Branded share of reported non-brand revenue", "v": render.pct(a["branded_share_of_nonbrand_value"])},
                  {"m": "True new-customer ROAS (branded terms stripped out of every campaign)", "v": render.ratio(a["true_new_customer_roas"])},
                  {"m": "Reverse leak (non-branded cost inside brand campaigns)", "v": render.money(a["reverse_leak_cost"], currency)},
              ], ["m", "v"], ["Measure", "Value"]),
              ""]
    lines.append(("FLAG: branded share of non-brand revenue is above " + render.pct(a["flag_share"]) + ". Apply the branded negative list to every non-brand campaign and re-run.")
                 if a["flag"] else "Branded share of non-brand revenue is under the flag threshold.")
    if result["assumptions"]:
        lines += ["", "## Assumptions", ""] + [f"- {s}" for s in result["assumptions"]]
    return "\n".join(lines) + "\n"

def cmd_leakage(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    data = io.load_workspace(ws)
    brand = Brand.from_workspace(data)
    camps = io.require(ws / "exports" / "campaigns.csv", ["campaign.name", "metrics.cost_micros", "metrics.conversions_value"])
    terms = io.require(ws / "exports" / "search_terms.csv", ["search_term_view.search_term", "campaign.name", "metrics.cost_micros", "metrics.conversions_value"])
    kw_path = ws / "exports" / "keywords.csv"
    keywords = io.read_csv(kw_path) if kw_path.exists() else None
    result = compute(camps, terms, brand, keywords, flag_share=args.flag_share, windows={
        "window_start": data.get("window_start"),
        "window_end": data.get("window_end"),
        "search_terms_window_start": data.get("search_terms_window_start"),
    })
    out = io.run_dir(ws, args.run_date)
    (out / "leakage.md").write_text(render_md(result, data.get("currency", "")))
    (out / "leakage.json").write_text(json.dumps(result, indent=2))
    a = result["account"]
    print(f"leakage: blended {render.ratio(a['blended_roas'])}, reported non-brand {render.ratio(a['reported_nonbrand_roas'])}, "
          f"true new-customer {render.ratio(a['true_new_customer_roas'])}, branded share {render.pct(a['branded_share_of_nonbrand_value'])}"
          f"{' FLAG' if a['flag'] else ''} -> {out / 'leakage.md'}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("leakage", help="branded leakage and true new-customer ROAS")
    p.add_argument("--flag-share", type=float, default=0.20, help="flag when branded share of non-brand revenue exceeds this fraction")
    add_common(p)
    p.set_defaults(func=cmd_leakage)
