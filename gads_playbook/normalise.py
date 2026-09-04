"""Detect Google Ads UI exports and map them to the canonical schema (spec section 6.1)."""
import re, shutil
from pathlib import Path
from . import io, schema

class UnknownReport(Exception):
    pass

TITLE_PATTERNS = [
    (re.compile(r"^campaign report", re.I), "campaigns"),
    (re.compile(r"^search terms? report", re.I), "search_terms"),
    (re.compile(r"^(search )?keywords? report", re.I), "keywords"),
    (re.compile(r"^product report", re.I), "products"),
    (re.compile(r"^conversion actions?", re.I), "conversion_actions"),
]

# canonical column -> (list of accepted UI labels, converter name)
MAPPINGS = {
    "campaigns": {
        "segments.date": (["Day", "Date"], "text"),
        "campaign.id": (["Campaign ID"], "text"),
        "campaign.name": (["Campaign"], "text"),
        "campaign.status": (["Campaign state", "Campaign status"], "enum"),
        "campaign.advertising_channel_type": (["Campaign type"], "channel"),
        "campaign.bidding_strategy_type": (["Bid strategy type", "Bidding strategy type"], "enum"),
        "campaign_budget.amount_micros": (["Budget"], "money"),
        "metrics.impressions": (["Impr.", "Impressions"], "int"),
        "metrics.clicks": (["Clicks"], "int"),
        "metrics.cost_micros": (["Cost"], "money"),
        "metrics.conversions": (["Conversions", "Conv."], "float"),
        "metrics.conversions_value": (["Conv. value", "Conversion value", "All conv. value"], "value"),
        "metrics.search_impression_share": (["Search impr. share", "Search impression share"], "pct"),
        "metrics.search_budget_lost_impression_share": (["Search lost IS (budget)"], "pct"),
        "metrics.search_rank_lost_impression_share": (["Search lost IS (rank)"], "pct"),
    },
    "search_terms": {
        "campaign.id": (["Campaign ID"], "text"),
        "campaign.name": (["Campaign"], "text"),
        "ad_group.id": (["Ad group ID"], "text"),
        "ad_group.name": (["Ad group"], "text"),
        "search_term_view.search_term": (["Search term"], "text"),
        "segments.search_term_match_type": (["Match type", "Search terms match type"], "match"),
        "metrics.impressions": (["Impr.", "Impressions"], "int"),
        "metrics.clicks": (["Clicks"], "int"),
        "metrics.cost_micros": (["Cost"], "money"),
        "metrics.conversions": (["Conversions", "Conv."], "float"),
        "metrics.conversions_value": (["Conv. value", "Conversion value"], "value"),
    },
    "keywords": {
        "campaign.id": (["Campaign ID"], "text"),
        "campaign.name": (["Campaign"], "text"),
        "ad_group.id": (["Ad group ID"], "text"),
        "ad_group.name": (["Ad group"], "text"),
        "ad_group_criterion.criterion_id": (["Keyword ID", "Criterion ID"], "text"),
        "ad_group_criterion.keyword.text": (["Keyword", "Search keyword"], "text"),
        "ad_group_criterion.keyword.match_type": (["Match type"], "match"),
        "ad_group_criterion.status": (["Keyword status", "Status"], "enum"),
        "ad_group_criterion.quality_info.quality_score": (["Quality score", "Quality Score"], "text"),
        "metrics.impressions": (["Impr.", "Impressions"], "int"),
        "metrics.clicks": (["Clicks"], "int"),
        "metrics.cost_micros": (["Cost"], "money"),
        "metrics.conversions": (["Conversions", "Conv."], "float"),
        "metrics.conversions_value": (["Conv. value", "Conversion value"], "value"),
    },
    "products": {
        "campaign.id": (["Campaign ID"], "text"),
        "campaign.name": (["Campaign"], "text"),
        "segments.product_item_id": (["Item ID", "Item Id"], "text"),
        "segments.product_title": (["Title", "Product title"], "text"),
        "segments.product_brand": (["Brand"], "text"),
        "metrics.impressions": (["Impr.", "Impressions"], "int"),
        "metrics.clicks": (["Clicks"], "int"),
        "metrics.cost_micros": (["Cost"], "money"),
        "metrics.conversions": (["Conversions", "Conv."], "float"),
        "metrics.conversions_value": (["Conv. value", "Conversion value"], "value"),
    },
    "conversion_actions": {
        "conversion_action.id": (["Conversion action ID"], "text"),
        "conversion_action.name": (["Conversion action", "Conversion action name"], "text"),
        "conversion_action.category": (["Category", "Conversion action category"], "enum"),
        "conversion_action.type": (["Type", "Conversion source", "Source"], "enum"),
        "conversion_action.status": (["Status"], "enum"),
        "conversion_action.primary_for_goal": (["Primary for goal", "Primary action"], "bool"),
        "conversion_action.counting_type": (["Counting", "Count"], "enum"),
        "conversion_action.click_through_lookback_window_days": (["Click-through conversion window", "Click-through window"], "days"),
        "conversion_action.view_through_lookback_window_days": (["View-through conversion window", "View-through window"], "days"),
        "conversion_action.attribution_model_settings.attribution_model": (["Attribution model"], "enum"),
        "conversion_action.include_in_conversions_metric": (['Include in "Conversions"', "Include in Conversions"], "bool"),
        "conversion_action.phone_call_duration_seconds": (["Call duration (seconds)", "Call length (seconds)"], "text"),
        "conversion_action.value_settings.default_value": (["Default value", "Value"], "text"),
    },
}

REQUIRED = {
    "campaigns": ["segments.date", "campaign.name", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value"],
    "search_terms": ["search_term_view.search_term", "campaign.name", "metrics.clicks", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value"],
    "keywords": ["ad_group_criterion.keyword.text", "campaign.name", "metrics.clicks"],
    "products": ["segments.product_item_id", "metrics.cost_micros", "metrics.conversions_value"],
    "conversion_actions": ["conversion_action.name"],
}

HEADER_HINTS = [("Search term", "search_terms"), ("Item ID", "products"), ("Conversion action", "conversion_actions"),
                ("Keyword", "keywords"), ("Search keyword", "keywords"), ("Day", "campaigns"), ("Campaign", "campaigns")]

def detect_report(first_lines):
    for line in first_lines[:3]:
        for pat, t in TITLE_PATTERNS:
            if pat.search(line.strip().strip('"')):
                return t
    for line in first_lines[:3]:
        cells = [c.strip().strip('"') for c in line.split(",")]
        for hint, t in HEADER_HINTS:
            if hint in cells:
                return t
    raise UnknownReport("unrecognised export. Recognised types: " + ", ".join(schema.REPORT_TYPES) +
                        ". Export from the Campaigns, Search terms, Search keywords, Products, or Conversions pages.")

def _channel(v):
    v = (v or "").strip().lower()
    return {"search": "SEARCH", "performance max": "PERFORMANCE_MAX", "shopping": "SHOPPING", "display": "DISPLAY",
            "video": "VIDEO", "demand gen": "DEMAND_GEN", "discovery": "DEMAND_GEN", "app": "MULTI_CHANNEL"}.get(v, v.upper().replace(" ", "_"))

def _match(v):
    v = (v or "").strip().lower().replace(" match", "")
    return {"exact": "EXACT", "phrase": "PHRASE", "broad": "BROAD", "exact (close variant)": "NEAR_EXACT",
            "phrase (close variant)": "NEAR_PHRASE"}.get(v, v.upper().replace(" ", "_"))

def _enum(v):
    return (v or "").strip().upper().replace(" ", "_").replace("-", "_")

def _bool(v):
    return "true" if (v or "").strip().lower() in ("yes", "true", "y", "1") else ("false" if (v or "").strip() else "")

def _days(v):
    n = io.parse_number(v)
    return str(int(n)) if (v or "").strip() and n else ("" if not (v or "").strip() else "0")

def _fmt(kind, v):
    if kind == "text":
        return (v or "").strip()
    if kind == "money":
        m = io.money_to_micros(v)
        return "" if m is None else str(m)
    if kind == "int":
        return str(int(io.parse_number(v))) if (v or "").strip() not in ("", "--") else ""
    if kind in ("float", "value"):
        return str(float(io.parse_number(v))) if (v or "").strip() not in ("", "--") else ""
    if kind == "pct":
        p = io.parse_percent(v)
        return "" if p is None else str(round(p, 6))
    return {"enum": _enum, "channel": _channel, "match": _match, "bool": _bool, "days": _days}[kind](v)

def normalise_rows(report_type, rows):
    mapping = MAPPINGS[report_type]
    if not rows:
        return []
    header = list(rows[0].keys())
    resolved = {}
    for canon, (labels, kind) in mapping.items():
        for lab in labels:
            if lab in header:
                resolved[canon] = (lab, kind)
                break
    missing = [c for c in REQUIRED[report_type] if c not in resolved]
    if missing:
        wanted = ["/".join(mapping[c][0]) for c in missing]
        raise io.MissingInput(f"{report_type} export is missing columns: {', '.join(wanted)}. Add them in the Google Ads column picker and export again.")
    out = []
    for r in rows:
        first = next(iter(r.values()), "") or ""
        if str(first).strip().lower().startswith("total"):
            continue
        if all((v or "").strip() == "" for v in r.values()):
            continue
        row = {}
        for canon in schema.COLUMNS[report_type]:
            if canon in resolved:
                lab, kind = resolved[canon]
                row[canon] = _fmt(kind, r.get(lab))
            else:
                row[canon] = ""
        out.append(row)
    return out

def normalise_file(path):
    path = Path(path)
    text = io._decode(path)
    lines = text.splitlines()
    report_type = detect_report(lines)
    # drop title lines until the header (the first line containing a known label)
    start = 0
    labels = {lab for cols in MAPPINGS[report_type].values() for lab in cols[0]}
    for i, line in enumerate(lines[:5]):
        cells = {c.strip().strip('"') for c in line.split(",")}
        if cells & labels:
            start = i
            break
    rows = io.read_csv_lines(lines[start:])
    return report_type, normalise_rows(report_type, rows)

def normalise_into_workspace(paths, ws):
    ws = Path(ws)
    written = {}
    for p in paths:
        p = Path(p)
        report_type, rows = normalise_file(p)
        out = ws / "exports" / f"{report_type}.csv"
        io.write_csv(out, rows, schema.COLUMNS[report_type])
        raw = ws / "raw" / p.name
        raw.parent.mkdir(parents=True, exist_ok=True)
        if raw.resolve() != p.resolve():
            shutil.copy2(p, raw)
        written[report_type] = out
    return written

def cmd_normalise(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    paths = []
    for a in args.paths:
        a = Path(a).expanduser()
        paths += sorted(a.glob("*.csv")) if a.is_dir() else [a]
    written = normalise_into_workspace(paths, ws)
    for t, p in written.items():
        print(f"{t}: {len(io.read_csv(p))} rows -> {p}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("normalise", help="convert Google Ads UI CSV exports into canonical exports/*.csv")
    p.add_argument("paths", nargs="+", help="export files or a folder of them")
    add_common(p)
    p.set_defaults(func=cmd_normalise)
