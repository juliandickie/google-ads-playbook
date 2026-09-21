"""gads audit: compose the audit report from whatever evidence the workspace holds (exports, the three
calculator runs, the settings deep pass, the brand SERP check, the reconciliation), with rule-drafted
recommendations for the gads-audit skill to review. Every source is optional; a missing one becomes a
named gap in the report and a "no evidence" verdict on the controls it would have decided. Writes
runs/<date>/audit.md (the document layout), audit.json, and audit-executive.md on request. The reviewer's
additions, edits and drops live in runs/<date>/audit-review.md and are merged on every run, so a rerun never
loses them. Read-only."""
import json, re
from collections import defaultdict
from datetime import date
from pathlib import Path
from . import io, schema

REFERENCES = Path(__file__).resolve().parents[1] / "references"
CHECKLIST = REFERENCES / "06-google-audit-checklist.md"

# Thresholds, practitioner defaults from the references. Override by editing here.
WASTE_MIN_COST = 10.0            # a zero-conversion term counts once it has spent this much (account currency)
WASTE_SHARE_FAIL = 0.15          # G16: zero-conversion share of visible term spend above this fails
WASTE_TOP_N = 9
CLICK_STRATEGY_FLOOR = 15        # conversions in the window past which Maximize Clicks should move on (02)
PMAX_FLOOR_PER_MONTH = 30        # G31
DEVICE_CPA_RATIO = 2.0           # mobile CPA at or above this multiple of desktop is a flag
DEVICE_MIN_CONV = 5.0
QS_PASS = 7.0                    # G20 impression-weighted quality score
TARGET_TOLERANCE = 0.2           # G37 tCPA within 20 percent of the 30-day CPA
KEYWORD_WASTE_CLICKS = 100       # G-WS1
STANDARD_WINDOW_DAYS = 90
CLICK_STRATEGIES = {"TARGET_SPEND", "MANUAL_CPC", "MAXIMIZE_CLICKS"}
CONVERSION_STRATEGIES = {"MAXIMIZE_CONVERSIONS", "TARGET_CPA"}
VALUE_STRATEGIES = {"MAXIMIZE_CONVERSION_VALUE", "TARGET_ROAS"}
DEAD_TYPES = {"UNIVERSAL_ANALYTICS_GOAL"}
UPLOAD_TYPES = {"UPLOAD_CLICKS", "UPLOAD_CALLS", "STORE_SALES", "STORE_SALES_DIRECT_UPLOAD"}
GA4_PURCHASE_TYPES = {"GOOGLE_ANALYTICS_4_PURCHASE"}
FIELD_ORDER = ["Campaign", "Issue", "Evidence", "Rule", "Confidence", "Change", "Owner", "Approval", "Risk", "Impact", "Rollback", "Window"]
DRAFT = "draft, needs the account manager's go"
OWNER = "the account manager"

GEO = {2036: "Australia", 2554: "New Zealand", 2840: "United States", 2124: "Canada", 2826: "United Kingdom",
       2276: "Germany", 2702: "Singapore", 2372: "Ireland", 2250: "France", 2380: "Italy", 2724: "Spain",
       2528: "Netherlands", 2056: "Belgium", 2756: "Switzerland", 2040: "Austria", 2752: "Sweden", 2578: "Norway",
       2208: "Denmark", 2246: "Finland", 2616: "Poland", 2620: "Portugal", 2442: "Luxembourg", 2438: "Liechtenstein",
       2352: "Iceland", 2392: "Japan", 2410: "South Korea", 2356: "India", 2784: "United Arab Emirates",
       2682: "Saudi Arabia", 2710: "South Africa", 2484: "Mexico", 2076: "Brazil", 2032: "Argentina",
       2152: "Chile", 2170: "Colombia", 2458: "Malaysia", 2764: "Thailand", 2608: "Philippines", 2360: "Indonesia",
       2704: "Vietnam", 2344: "Hong Kong", 2158: "Taiwan", 2376: "Israel", 2792: "Turkey", 2300: "Greece",
       2203: "Czechia", 2348: "Hungary", 2642: "Romania"}

# ---------------------------------------------------------------- helpers

def money(micros):
    return f"{(micros or 0) / 1_000_000:,.2f}"

def num(x, nd=2):
    return f"{x:,.{nd}f}"

def pct(x, nd=1):
    return f"{100 * x:.{nd}f} percent"

def roas(x):
    return f"{x:.2f}x" if x is not None else "n/a"

def geo_name(resource):
    try:
        gid = int(str(resource).split("/")[-1])
    except ValueError:
        return str(resource)
    return GEO.get(gid, f"location {gid}")

def parse_checklist(path=CHECKLIST):
    """The control table from references/06: (section, id, name, severity) in file order."""
    out, section = [], ""
    if not Path(path).exists():
        return out
    for line in Path(path).read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"^\|\s*(G[-A-Z]*\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            out.append((section, m.group(1), m.group(2), m.group(3)))
    return out

# ---------------------------------------------------------------- evidence

class Evidence:
    """Everything the workspace holds for this run, each source optional and its absence recorded."""
    def __init__(self, ws, run_date=None, deep=None):
        self.ws = Path(ws)
        self.data = io.load_workspace(self.ws)
        self.run_date = run_date or date.today().isoformat()
        self.currency = self.data.get("currency", "")
        self.missing = []       # (source, why it matters)
        self.used = []          # relative paths that fed the report
        self.exports = {}
        for name in schema.REPORT_TYPES:
            p = self.ws / "exports" / f"{name}.csv"
            if p.exists():
                self.exports[name] = io.read_csv(p)
                self.used.append(f"exports/{name}.csv")
            else:
                self.missing.append((f"exports/{name}.csv", "run gads pull"))
        self.run_dir = self.ws / "runs" / self.run_date
        self.leakage = self._json(self.run_dir / "leakage.json", "gads leakage")
        self.misallocation = self._json(self.run_dir / "misallocation.json", "gads misallocate")
        self.windows = self._json(self.run_dir / "windows.json", "gads windows")
        self.brand_serp, self.brand_serp_from = self._latest("brand-serp.md", "the brand SERP check (gads skill)")
        self.reconciliation, self.reconciliation_from = self._latest("reconciliation.md", "the reconciliation (gads-audit 1.1)")
        self.deep_dir, self.manifest, self.deep_files = None, None, {}
        candidates = [self.ws / "raw" / f"deep-{deep}"] if deep else sorted((self.ws / "raw").glob("deep-*")) if (self.ws / "raw").exists() else []
        candidates = [c for c in candidates if c.is_dir()]
        if candidates:
            self.deep_dir = candidates[-1]
            self.manifest = self._json(self.deep_dir / "manifest.json", "gads pull --deep") or {}
            for p in sorted(self.deep_dir.glob("*.json")):
                if p.name == "manifest.json" or p.name.startswith("scratch"):
                    continue
                try:
                    self.deep_files[p.stem] = json.loads(p.read_text())
                    self.used.append(self.rel(p))
                except json.JSONDecodeError:
                    self.missing.append((self.rel(p), "unreadable JSON"))
            for name, entry in (self.manifest.get("queries") or {}).items():
                if entry.get("error"):
                    self.missing.append((self.rel(self.deep_dir / f"{name}.error.txt"), "the API rejected the query; see the file"))
        else:
            self.missing.append(("raw/deep-<date>/", "run gads pull --deep for settings, negatives, ads, audiences, goals, per-action volumes, devices, geos, landing pages, change events"))

    def _json(self, p, producer):
        if p.exists():
            self.used.append(self.rel(p))
            return json.loads(p.read_text())
        self.missing.append((self.rel(p), producer))
        return None

    def _latest(self, filename, producer):
        """The file from this run, else the newest earlier run that has it (a SERP check or a reconciliation
        holds for weeks); returns (text, the run date it came from) or (None, None) and records the gap."""
        p = self.run_dir / filename
        if p.exists():
            self.used.append(self.rel(p))
            return p.read_text(), self.run_date
        runs = self.ws / "runs"
        earlier = sorted(d for d in runs.glob("*/" + filename) if d.parent.name <= self.run_date and d.parent.name != self.run_date) if runs.exists() else []
        if earlier:
            q = earlier[-1]
            self.used.append(self.rel(q))
            return q.read_text(), q.parent.name
        self.missing.append((self.rel(p), producer))
        return None, None

    def _text(self, p, producer):
        if p.exists():
            self.used.append(self.rel(p))
            return p.read_text()
        self.missing.append((self.rel(p), producer))
        return None

    def rel(self, p):
        try:
            return str(Path(p).relative_to(self.ws))
        except ValueError:
            return str(p)

    def deep(self, name):
        return self.deep_files.get(name)

    def link(self, relpath, label=None):
        target = self.ws / relpath
        label = label or Path(relpath).name
        return f"[{label}](file://{target})"

    def export(self, name):
        return self.exports.get(name)

    def calc(self, name):
        """The calculator's markdown when it exists (the readable twin), else its JSON."""
        md = self.run_dir / f"{name}.md"
        return f"runs/{self.run_date}/{name}.md" if md.exists() else f"runs/{self.run_date}/{name}.json"

# ---------------------------------------------------------------- report model

class Report:
    def __init__(self, ev):
        self.ev = ev
        self.sections = defaultdict(list)     # section -> [(label, text)]
        self.recs = []                        # dicts with FIELD_ORDER keys plus title, section
        self.controls = {}                    # id -> (verdict, note)
        self.headline = {}                    # numbers the executive version reuses
        self.campaigns = []                   # per-campaign role blocks [(name, [(label, text)])]
        self.caveats = []                     # reviewer caveats [(label, text)]
        self.review_notes = []                # what the review merge could not place
        self.review = None

    def add(self, section, label, text):
        self.sections[section].append((label, text))

    def rec(self, section, title, **fields):
        r = {"section": section, "title": title}
        for k in FIELD_ORDER:
            r[k] = fields.get(k, "")
        r.setdefault("Owner", OWNER)
        if not r["Owner"]:
            r["Owner"] = OWNER
        if not r["Approval"]:
            r["Approval"] = DRAFT
        self.recs.append(r)
        return r

    def control(self, cid, verdict, note=""):
        self.controls[cid] = (verdict, note)

# ---------------------------------------------------------------- aggregation helpers

def campaign_totals(rows):
    """campaigns.csv rows (per date) aggregated per campaign name."""
    out = {}
    for r in rows:
        name = r["campaign.name"]
        c = out.setdefault(name, {"status": r.get("campaign.status", ""), "channel": r.get("campaign.advertising_channel_type", ""),
                                  "strategy": r.get("campaign.bidding_strategy_type", ""), "budget": io.parse_number(r.get("campaign_budget.amount_micros")),
                                  "cost": 0.0, "conversions": 0.0, "value": 0.0, "clicks": 0.0, "impressions": 0.0})
        c["cost"] += io.parse_number(r.get("metrics.cost_micros"))
        c["conversions"] += io.parse_number(r.get("metrics.conversions"))
        c["value"] += io.parse_number(r.get("metrics.conversions_value"))
        c["clicks"] += io.parse_number(r.get("metrics.clicks"))
        c["impressions"] += io.parse_number(r.get("metrics.impressions"))
        if r.get("campaign.status"):
            c["status"] = r["campaign.status"]
    return out

def enabled_names(totals, settings):
    if settings:
        return sorted({r["campaign.name"] for r in settings if r.get("campaign.status") == "ENABLED"})
    return sorted(n for n, c in totals.items() if c["status"] == "ENABLED")

def by_campaign(rows, key="campaign.name"):
    out = defaultdict(list)
    for r in rows or []:
        out[r.get(key, "")].append(r)
    return out

# ---------------------------------------------------------------- rules

def rule_overview(rep):
    ev = rep.ev
    rows = ev.export("campaigns")
    if not rows:
        rep.add("overview", "Campaigns", "no campaigns.csv in the workspace; run gads pull. Nothing below can size the account.")
        return {}
    totals = campaign_totals(rows)
    settings = ev.deep("campaign_settings")
    enabled = enabled_names(totals, settings)
    channels = sorted({c["channel"] for n, c in totals.items() if n in enabled})
    cost = sum(c["cost"] for c in totals.values()); value = sum(c["value"] for c in totals.values()); conv = sum(c["conversions"] for c in totals.values())
    en_cost = sum(totals[n]["cost"] for n in enabled if n in totals)
    rep.headline.update({"window": f"{ev.data.get('window_start', '?')} to {ev.data.get('window_end', '?')}", "cost": cost, "value": value,
                         "conversions": conv, "roas": (value / (cost / 1e6)) if cost else None, "enabled": len(enabled), "total": len(totals),
                         "currency": ev.currency})
    rep.add("overview", "Shape of the account", f"{len(enabled)} enabled campaigns ({', '.join(channels) or 'channel unknown'}) of {len(totals)} with spend in the window; "
            f"{sum(1 for n, c in totals.items() if c['status'] == 'PAUSED')} paused. "
            + ("No Performance Max campaign. " if not any(c['channel'] == 'PERFORMANCE_MAX' for c in totals.values()) else "")
            + ("No Shopping campaign. " if not any(c['channel'] == 'SHOPPING' for c in totals.values()) else ""))
    rep.add("overview", f"Window {rep.headline['window']}", f"cost {money(cost)}, {num(conv, 1)} conversions, value {num(value, 0)}, blended ROAS {roas(rep.headline['roas'])}. "
            f"The enabled campaigns carry {money(en_cost)} of that. Source: {ev.link('exports/campaigns.csv')}.")
    if totals:
        top = max(((n, c) for n, c in totals.items() if n in enabled or not enabled), key=lambda nc: nc[1]["cost"], default=None)
        if top:
            n, c = top
            rep.add("overview", "The biggest spender", f"{n}, {money(c['cost'])} cost, {num(c['conversions'], 1)} conversions, {num(c['value'], 0)} value, "
                    f"{roas(c['value'] / (c['cost'] / 1e6)) if c['cost'] else 'n/a'}.")
    if ev.windows and ev.windows.get("account"):
        w30 = ev.windows["account"]["windows"].get("30", {})
        cur, prior = w30.get("cur", {}), w30.get("prior", {})
        delta = w30.get("delta_roas")
        rep.headline.update({"roas_30": cur.get("roas"), "roas_30_prior": prior.get("roas"), "cost_30": cur.get("cost"), "conv_30": cur.get("conversions"),
                             "delta_30": delta, "target_roas": ev.windows.get("target_roas"), "breakeven_roas": ev.windows.get("breakeven_roas")})
        verdicts = defaultdict(list)
        for c in ev.windows.get("campaigns", []):
            verdicts[c["verdict"]].append(c["campaign"])
        rep.headline["verdicts"] = dict(verdicts)
        rep.add("overview", "Last 30 days", f"cost {money(cur.get('cost'))}, {num(cur.get('conversions') or 0, 1)} conversions, ROAS {roas(cur.get('roas'))}"
                + (f", {'down' if delta < 0 else 'up'} {abs(delta) * 100:.1f} percent on the prior 30 days ({roas(prior.get('roas'))})" if delta is not None else "")
                + f". Against the {ev.windows.get('target_roas')}x target: " + ", ".join(f"{len(v)} {k}" for k, v in verdicts.items())
                + f". Source: {ev.link(ev.calc('windows'))}, Account table.")
    else:
        rep.add("overview", "Last 30 days", "no windows.json for this run date; run gads windows.")
    return totals

def _actions(ev):
    """Enabled conversion actions as dicts with common keys, from the deep pass or the export."""
    full = ev.deep("conversion_actions_full")
    src = None
    if full:
        rows, src = full, ev.rel(ev.deep_dir / "conversion_actions_full.json")
    elif ev.export("conversion_actions"):
        rows, src = ev.export("conversion_actions"), "exports/conversion_actions.csv"
    else:
        return [], None
    out = []
    for r in rows:
        if str(r.get("conversion_action.status", "")).upper() != "ENABLED":
            continue
        out.append({"id": str(r.get("conversion_action.id", "")), "name": r.get("conversion_action.name", ""), "type": r.get("conversion_action.type", ""),
                    "category": r.get("conversion_action.category", ""), "primary": str(r.get("conversion_action.primary_for_goal", "")).lower() in ("true", "1"),
                    "click_window": io.parse_number(r.get("conversion_action.click_through_lookback_window_days")),
                    "model": r.get("conversion_action.attribution_model_settings.attribution_model", ""),
                    "default_always": str(r.get("conversion_action.value_settings.always_use_default_value", "")).lower() == "true",
                    "default_value": io.parse_number(r.get("conversion_action.value_settings.default_value"))})
    return out, src

def rule_tracking(rep, totals):
    ev, S = rep.ev, "tracking"
    actions, src = _actions(ev)
    if not actions:
        rep.add(S, "Conversion actions", "no conversion_actions.csv and no deep pass; nothing here can be judged. Run gads pull (and --deep).")
        for cid in ("G42", "G46", "G47", "G48", "G49", "G-CT1", "G-CT2"):
            rep.control(cid, "no evidence", "no conversion action data")
        return
    vol = ev.deep("conversion_action_metrics_90d")
    volumes = {str(r.get("conversion_action.id")): r for r in vol} if vol else {}
    vol_src = ev.rel(ev.deep_dir / "conversion_action_metrics_90d.json") if vol else None
    primaries = [a for a in actions if a["primary"]]
    purchases = [a for a in actions if a["category"] == "PURCHASE"]
    fired = []
    if volumes:
        for a in actions:
            v = volumes.get(a["id"], {})
            a["all_conversions"] = io.parse_number(v.get("metrics.all_conversions"))
            a["all_value"] = io.parse_number(v.get("metrics.all_conversions_value"))
            if a["all_conversions"] > 0:
                fired.append(a)
    goals = ev.deep("customer_conversion_goals")
    biddable = sorted({g["customer_conversion_goal.category"] for g in goals if g.get("customer_conversion_goal.biddable")}) if goals else []
    rep.add(S, "Enabled actions", f"{len(actions)} enabled, {len(primaries)} primary" + (f", {len(biddable)} biddable categories at account level ({', '.join(biddable)})" if biddable else "")
            + f". Source: {ev.link(src)}" + (f", {ev.link(ev.rel(ev.deep_dir / 'customer_conversion_goals.json'))}" if goals else "") + ".")
    rep.control("G42", "pass" if primaries else "fail", f"{len(primaries)} primary")
    if volumes:
        m = ev.manifest.get("windows", {}).get("metrics", ["?", "?"]) if ev.manifest else ["?", "?"]
        lines = "; ".join(f"\"{a['name']}\" ({a['category']}, {'primary' if a['primary'] else 'secondary'}) {num(a['all_conversions'], 1)} worth {num(a['all_value'], 2)}" for a in sorted(fired, key=lambda a: -a["all_conversions"]))
        rep.add(S, f"What fired, {m[0]} to {m[1]}", f"{len(fired)} of {len(actions)} enabled actions recorded anything: {lines or 'none'}. Source: {ev.link(vol_src)}.")
        prim_fired = [a for a in fired if a["primary"]]
        prim_total = sum(a["all_conversions"] for a in prim_fired)
        non_purchase = sum(a["all_conversions"] for a in prim_fired if a["category"] != "PURCHASE")
        purchase_fired = [a for a in fired if a["category"] == "PURCHASE"]
        rep.headline["purchases_90d"] = sum(a["all_conversions"] for a in purchase_fired)
        rep.headline["purchase_value_90d"] = sum(a["all_value"] for a in purchase_fired)
        rep.headline["primary_90d"] = prim_total
        rep.headline["non_purchase_primary_90d"] = non_purchase
        if prim_total:
            rep.add(S, "What Smart Bidding optimises to", f"{num(non_purchase, 1)} of the {num(prim_total, 1)} primary conversions are not purchases ({pct(non_purchase / prim_total)}).")
    else:
        rep.add(S, "What fired", "no per-action volumes (the deep pass file conversion_action_metrics_90d.json); which actions actually record cannot be seen from configuration alone.")
    # G47: one primary, purchase
    if len(primaries) == 1 and primaries[0]["category"] == "PURCHASE":
        rep.control("G47", "pass", "one primary, a purchase")
    elif not primaries:
        rep.control("G47", "fail", "no primary")
    else:
        rep.control("G47", "fail", f"{len(primaries)} primaries, categories {', '.join(sorted({a['category'] for a in primaries}))}")
        best = max((a for a in purchases if a.get("all_value") is not None), key=lambda a: a.get("all_value", 0), default=None) if volumes else (purchases[0] if purchases else None)
        target = f'"{best["name"]}"' if best else "the purchase action"
        conv_campaigns = [n for n, c in totals.items() if c["status"] == "ENABLED" and c["strategy"] in CONVERSION_STRATEGIES]
        rep.rec(S, "One primary action, the purchase",
                Campaign="all", Issue=f"{len(primaries)} primary actions" + (f" across {len(biddable)} biddable categories" if biddable else "") + " where the standard is one, the purchase.",
                Evidence=f"{ev.link(src)} (primary_for_goal)" + (f", {ev.link(vol_src)}" if vol_src else ""),
                Rule="02 Measurement Standard, 06 G47", Confidence="high",
                Change=f"Make {target} the only primary; set every signup, lead, contact, booking, download and page-view action to secondary."
                       + (f" Move {', '.join(conv_campaigns)} from Maximize Conversions to Maximize Conversion Value with a tROAS at three quarters of the target for the first 30 days." if conv_campaigns else ""),
                Risk="the conversion volume Smart Bidding sees drops to purchases only, so learning slows; keep the secondary column visible and read 30-day windows.",
                Impact="the algorithm stops buying whatever the cheapest primary was and starts buying purchases.", Rollback="flip the primary flags back.", Window="30 days, then the 7, 14, 30 gate.")
    # dead actions
    if volumes:
        dead = [a for a in actions if a.get("all_conversions", 0) == 0]
        dead_types = defaultdict(int)
        for a in dead:
            dead_types[a["type"]] += 1
        if dead:
            rep.add(S, "Enabled but silent", f"{len(dead)} enabled actions recorded nothing in the window: " + ", ".join(f"{n} {t}" for t, n in sorted(dead_types.items(), key=lambda x: -x[1])) + f"; {sum(1 for a in dead if a['primary'])} of them primary.")
            ua = [a for a in dead if a["type"] in DEAD_TYPES]
            rep.rec(S, "Remove the actions that cannot fire", Campaign="account",
                    Issue=f"{len(dead)} enabled actions at zero in the window, {len(ua)} of them Universal Analytics goals that stopped processing in 2024; {sum(1 for a in dead if a['primary'])} still primary.",
                    Evidence=f"{ev.link(vol_src)}, {ev.link(src)}", Rule="07 (an enabled action that cannot fire is noise, not measurement)", Confidence="high",
                    Change=f"Set the {len(ua)} Universal Analytics goals to removed" + (", then decide each remaining silent action: keep it secondary if it is expected to fire, remove it if the source is dead." if len(dead) > len(ua) else "."),
                    Risk="none to bidding, they record nothing.", Impact="a readable conversion list, no accidental primary page-view goals.", Rollback="re-enable.", Window="immediate.")
    else:
        ua = [a for a in actions if a["type"] in DEAD_TYPES]
        if ua:
            rep.rec(S, "Remove the Universal Analytics goals", Campaign="account", Issue=f"{len(ua)} Universal Analytics goals still enabled ({sum(1 for a in ua if a['primary'])} primary); Universal Analytics stopped processing in 2024.",
                    Evidence=ev.link(src), Rule="07", Confidence="high", Change=f"Set all {len(ua)} to removed.", Risk="none.", Impact="a readable conversion list.", Rollback="re-enable.", Window="immediate.")
    # windows and attribution
    judged = {a['id']: a for a in fired + primaries}.values()
    windows_set = sorted({int(a["click_window"]) for a in judged if a["click_window"]})
    models = sorted({a["model"] for a in judged if a["model"]})
    if len(windows_set) > 1 or (windows_set and windows_set[0] < STANDARD_WINDOW_DAYS):
        rep.control("G46", "warning", f"click windows {', '.join(map(str, windows_set))} days across the actions that matter")
    elif windows_set:
        rep.control("G46", "pass", f"{windows_set[0]}-day click window")
    if len(models) > 1:
        rep.control("G48", "warning", f"attribution models mixed: {', '.join(models)}")
    elif models:
        rep.control("G48", "pass" if "DATA_DRIVEN" in models[0] else "warning", models[0])
    if len(windows_set) > 1 or len(models) > 1:
        rep.add(S, "Windows and models", f"click windows {', '.join(map(str, windows_set)) or 'unknown'} days; attribution {', '.join(models) or 'unknown'}. Source: {ev.link(src)}.")
        rep.rec(S, "Matched windows and attribution", Campaign="account", Issue="click windows and attribution models differ across the actions that record.",
                Evidence=f"{ev.link(src)} (click_through_lookback_window_days, attribution_model)", Rule="02 matched windows, 06 G46 and G48", Confidence="high",
                Change=f"A {STANDARD_WINDOW_DAYS}-day click window on every action that stays enabled and data-driven attribution wherever Google allows it.",
                Risk="window changes restate history.", Impact="campaigns become comparable.", Rollback="restore per action.", Window="immediate.")
    # duplicate purchase primaries, default values, GA4 import
    pp = [a for a in primaries if a["category"] == "PURCHASE"]
    rep.control("G-CT1", "warning" if len(pp) > 1 else ("pass" if pp else "no evidence"), f"{len(pp)} primary purchase actions" if pp else "no primary purchase action")
    if len(pp) > 1:
        rep.add(S, "Duplicate purchase primaries", f"{len(pp)} primary PURCHASE actions ({', '.join(a['name'] for a in pp)}); any two that fire on the same order double count.")
    dv = [a for a in primaries if a["default_always"]]
    rep.control("G49", "warning" if dv else ("pass" if actions else "no evidence"), f"{len(dv)} primary actions on a fixed default value" if dv else "values carried per conversion")
    ga4 = [a for a in actions if a["type"] in GA4_PURCHASE_TYPES]
    if ga4 and volumes:
        silent = [a for a in ga4 if a.get("all_conversions", 0) == 0]
        if silent:
            rep.control("G-CT2", "warning", "a GA4 purchase import records zero")
            rep.rec(S, "The GA4 purchase import records zero", Campaign="account",
                    Issue=f"\"{silent[0]['name']}\" is enabled and recorded nothing in the window while the account has purchases elsewhere.",
                    Evidence=ev.link(vol_src), Rule="06 G-CT2; gads-audit 1.1 (check attribution before the link)", Confidence="medium",
                    Change="In GA4, run purchases by session source and by first-user source. If a hosted checkout on another domain carries the purchases and every one is Direct, add that domain to cross-domain measurement (data stream, configure your domains, unwanted referrals). Only then does the import count; keep it secondary beside the upload that is primary.",
                    Risk="none.", Impact="a tag-based backup that agrees with the primary within 15 percent.", Rollback="not applicable.", Window="30 days after the fix.")
        else:
            rep.control("G-CT2", "pass", "the GA4 purchase import records")
    elif ga4:
        rep.control("G-CT2", "no evidence", "a GA4 import exists; volumes need the deep pass")
    else:
        rep.control("G-CT2", "no evidence", "no GA4 purchase import")
    cust = ev.deep("customer")
    if cust:
        c = cust[0]
        ecl = c.get("customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled")
        rep.control("G43", "partial" if ecl else "warning", "enhanced conversions for leads on; purchases not visible through the API" if ecl else "enhanced conversions for leads off")
        rep.add(S, "Account settings", f"auto-tagging {'on' if c.get('customer.auto_tagging_enabled') else 'off'}; enhanced conversions for leads {'on' if ecl else 'off'}; conversion tracking {c.get('customer.conversion_tracking_setting.conversion_tracking_status', 'unknown')}. Source: {ev.link(ev.rel(ev.deep_dir / 'customer.json'))}.")
    else:
        rep.control("G43", "no evidence", "customer.json needs the deep pass")
    uploads = [a for a in fired if a["type"] in UPLOAD_TYPES] if volumes else [a for a in actions if a["type"] in UPLOAD_TYPES]
    rep.control("G44", "pass" if uploads else "no evidence", "offline uploads carry conversions" if uploads else "no upload or server-side path visible")
    rep.control("G45", "no evidence", "consent mode is not visible through the API")
    rep.control("G-CT3", "no evidence", "tag firing not checked on site")
    if ev.reconciliation:
        rep.add(S, "Reconciliation", f"{'done for this run' if ev.reconciliation_from == ev.run_date else 'from the ' + ev.reconciliation_from + ' run; redo it when the tracking changes'}, see {ev.link(f'runs/{ev.reconciliation_from}/reconciliation.md')}.")
    else:
        rep.add(S, "Reconciliation", "not done for this run. The measurement standard needs the attribution tool and the cart or CRM compared for one window (counts, leads, value, both currency directions when the currencies differ); write runs/<date>/reconciliation.md.")

def rule_leakage(rep, totals):
    ev, S = rep.ev, "leakage"
    L = ev.leakage
    if not L:
        rep.add(S, "Leakage", "no leakage.json for this run date; run gads leakage (needs brand_tokens in gads.json).")
        rep.control("G05", "no evidence", "no leakage run")
        return
    a = L["account"]
    rep.headline.update({"blended": a.get("blended_roas"), "true_roas": a.get("true_new_customer_roas"), "branded_share": a.get("branded_share_of_nonbrand_value")})
    lk = ev.link(ev.calc('leakage'))
    rep.add(S, "Blended ROAS (all campaigns)", roas(a.get("blended_roas")))
    rep.add(S, "Reported non-brand ROAS", roas(a.get("reported_nonbrand_roas")))
    rep.add(S, "Branded share of reported non-brand revenue", pct(a.get("branded_share_of_nonbrand_value") or 0))
    rep.add(S, "True new-customer ROAS (branded terms stripped out of every campaign)", roas(a.get("true_new_customer_roas")))
    rep.add(S, "Reverse leak (non-branded cost inside brand campaigns)", f"{ev.currency} {money(a.get('reverse_leak_cost'))}")
    branded = [c for c in L["per_campaign"] if c.get("kind") != "brand" and (c.get("branded_cost") or 0) > 0]
    brand_camps = [c for c in L["per_campaign"] if c.get("kind") == "brand"]
    rep.add(S, "Reading", (f"{len(brand_camps)} brand campaign(s). " if brand_camps else "No brand campaign, so blended equals reported non-brand. ")
            + (f"Branded searches reach {len(branded)} non-brand campaigns: " + "; ".join(f"{c['campaign']} {money(c['branded_cost'])} (value {num(c['branded_value'], 0)})" for c in branded) + ". " if branded else "No branded cost inside the non-brand campaigns. ")
            + " ".join(L.get("assumptions", [])) + f" Source: {lk}.")
    serp_verdict = None
    if ev.brand_serp:
        low = ev.brand_serp.lower()
        serp_verdict = "protect" if "protect" in low and "no bid" not in low else ("mixed" if "protect" in low else "no bid")
        rep.add(S, "Brand SERP check", f"{'from this run' if ev.brand_serp_from == ev.run_date else 'from the ' + ev.brand_serp_from + ' run (the check holds until the monthly recheck)'}, verdict {serp_verdict}, see {ev.link(f'runs/{ev.brand_serp_from}/brand-serp.md')}.")
    else:
        rep.add(S, "Brand SERP check", "not run for this run date; the brand-bidding rule cannot be applied without it.")
    if branded:
        rep.control("G05", "warning", "brand searches bought inside non-brand campaigns")
        total_b = sum(c["branded_cost"] for c in branded)
        rep.rec(S, "Brand negatives on every non-brand campaign", Campaign=", ".join(c["campaign"] for c in branded),
                Issue=f"brand searches are bought inside non-brand campaigns, {money(total_b)} over the window.",
                Evidence=f"{lk} (branded cost column), {ev.link('exports/search_terms.csv')}" + (f", {ev.link(f'runs/{ev.brand_serp_from}/brand-serp.md')}" if ev.brand_serp else ""),
                Rule="the gads contract's brand-bidding rule (bid on brand only where not first organically or a competitor advertises)",
                Confidence="high" if serp_verdict == "no bid" else "medium",
                Change=f"Add the brand tokens ({', '.join(ev.data.get('brand_tokens', []))}) and their common variants as phrase negatives in a shared list \"Brand - do not bid\" applied to every non-brand campaign"
                       + ("." if serp_verdict == "no bid" else "; where the SERP check says protect, route those searches to a brand campaign instead."),
                Risk="the few conversions those searches produced arrive organically instead.", Impact=f"about {money(total_b)} per window back and cleaner non-brand data.", Rollback="detach the list.", Window="30 days, confirm via search terms.")
    else:
        rep.control("G05", "pass" if brand_camps else "not applicable", "brand negatives hold" if brand_camps else "no brand campaign and no branded cost in non-brand campaigns")
    if a.get("reverse_leak_cost"):
        rep.rec(S, "Non-brand terms inside the brand campaign", Campaign=", ".join(c["campaign"] for c in brand_camps), Issue=f"{money(a['reverse_leak_cost'])} of non-branded cost inside brand campaigns.",
                Evidence=lk, Rule="06 G05", Confidence="high", Change="Exact and phrase brand keywords only in the brand campaign; move the non-brand terms to the non-brand campaign or add them as negatives.",
                Risk="low.", Impact="a brand ROAS that means something.", Rollback="restore.", Window="30 days.")

def rule_pmax(rep, totals):
    ev, S = rep.ev, "pmax"
    if not totals:
        rep.control("G06", "no evidence", "no campaigns.csv")
        return
    pmax = [n for n, c in totals.items() if c["channel"] == "PERFORMANCE_MAX"]
    if pmax:
        rep.add(S, "Performance Max campaigns", ", ".join(pmax) + ". Brand exclusions and the two-campaign split are not visible through the exports; check them in the UI.")
        rep.control("G06", "partial" if len(pmax) < 2 else "pass", f"{len(pmax)} PMax campaign(s)")
        return
    rep.control("G06", "fail", "no PMax campaign")
    rep.add(S, "Finding", f"no Performance Max campaign exists, enabled or paused, so the two-campaign structure the locked decisions require (brand-allowed capture, brand-excluded scaling) is absent. Source: {ev.link('exports/campaigns.csv')} (channel types).")
    per_month = (rep.headline.get("purchases_90d") or 0) / 3 if rep.headline.get("purchases_90d") is not None else None
    if per_month is not None and per_month < PMAX_FLOOR_PER_MONTH:
        rep.add(S, "Why not now", f"06 G31 puts the floor for PMax at {PMAX_FLOOR_PER_MONTH} to 50 conversions a month and this account records about {per_month:.0f} purchases a month. A PMax launched today would learn from whatever else is primary. The locked decision in 02 is sequenced, not changed.")
        rep.rec(S, "One capture PMax, after tracking is fixed", Campaign="new", Issue="no remarketing pillar and no PMax, but the prerequisites are missing.",
                Evidence=f"{ev.link('exports/campaigns.csv')}" + (f", {ev.link(ev.rel(ev.deep_dir / 'conversion_action_metrics_90d.json'))}" if ev.deep('conversion_action_metrics_90d') else ""),
                Rule="02 PMax Rules and Decisions Locked 1; 06 G31", Confidence="medium",
                Change=f"After the tracking recommendations have run for 30 days, launch one PMax as the capture campaign only, brand exclusion on, the brand negative list attached, audience signals from the owned lists, a tROAS above the best search campaign, budget 10 percent of the account. Add the scaling campaign only when purchases reach {PMAX_FLOOR_PER_MONTH} a month.",
                Risk="PMax on thin purchase data drifts to cheap conversions; the high tROAS and single-primary tracking are the guard.", Impact="a warm-audience pillar the account lacks.", Rollback="pause.", Window="30 days after launch, then the gate.")
    else:
        rep.rec(S, "Build the two PMax campaigns", Campaign="new", Issue="the locked two-campaign structure does not exist.", Evidence=ev.link("exports/campaigns.csv"),
                Rule="02 Decisions Locked 1; 06 G06", Confidence="medium", Change="Create the brand-allowed capture campaign and the brand-excluded scaling campaign per 02, with the brand negative list on the scaling one.",
                Risk="learning period on both.", Impact="the structure the playbook scales.", Rollback="pause.", Window="30 days, then the gate.")

def rule_misallocation(rep, totals):
    ev, S = rep.ev, "misallocation"
    M = ev.misallocation
    if M:
        mk = ev.link(ev.calc('misallocation'))
        t = M.get("thresholds", {})
        rep.add(S, "Verdict", f"{len(M.get('winners', []))} underfunded winners, {len(M.get('losers', []))} overfunded losers at the default thresholds ({t.get('min_conversions')} conversions, CVR above {pct(t.get('win_cvr', 0), 0)} on under {pct(t.get('win_share', 0), 0)} share, CVR under {pct(t.get('lose_cvr', 0), 0)} on over {pct(t.get('lose_share', 0), 0)} share). Source: {mk}.")
        for w in M.get("winners", []):
            rep.rec(S, f"Fund the winner {w.get('term', w.get('search_term', ''))}", Campaign=w.get("campaign", ""), Issue=f"a term converting at {pct(w.get('cvr', 0))} holds {pct(w.get('share', 0))} of its campaign's cost.",
                    Evidence=mk, Rule="06 G16 in reverse (spend follows conversion)", Confidence="medium", Change="Give it its own ad group and a bid or budget that matches its conversion rate.",
                    Risk="the rate may not hold at volume.", Impact="more of the converting traffic.", Rollback="revert.", Window="14 days.")
        for l in M.get("losers", []):
            rep.rec(S, f"Cut the loser {l.get('term', l.get('search_term', ''))}", Campaign=l.get("campaign", ""), Issue=f"a term at {pct(l.get('cvr', 0))} CVR holds {pct(l.get('share', 0))} of its campaign's cost.",
                    Evidence=mk, Rule="06 G16", Confidence="medium", Change="Negative it or move it to its own ad group with a lower bid.", Risk="low.", Impact="spend back.", Rollback="remove the negative.", Window="14 days.")
        cov = M.get("coverage", [])
        if cov:
            tc = sum(c.get("term_cost", 0) for c in cov); cc = sum(c.get("campaign_cost", 0) for c in cov)
            rep.add(S, "Coverage", f"search terms cover {money(tc)} of {money(cc)} campaign cost ({pct(tc / cc) if cc else 'n/a'}); the thresholds only see the visible part.")
            rep.control("G19", "fail" if cc and tc / cc < 0.5 else "pass", f"{pct(tc / cc) if cc else 'n/a'} of spend visible as search terms")
    else:
        rep.add(S, "Verdict", "no misallocation.json for this run date; run gads misallocate.")
    terms = ev.export("search_terms")
    if not terms:
        rep.add(S, "Search terms", "no search_terms.csv; the waste and intent reads need it.")
        for cid in ("G16", "G17", "G-WS1"):
            rep.control(cid, "no evidence", "no search terms")
        return
    cost = lambda r: io.parse_number(r.get("metrics.cost_micros")) / 1e6
    conv = lambda r: io.parse_number(r.get("metrics.conversions"))
    visible = sum(cost(r) for r in terms)
    zero = [r for r in terms if conv(r) == 0 and cost(r) > WASTE_MIN_COST]
    zero_cost = sum(cost(r) for r in zero)
    share = zero_cost / visible if visible else 0
    top = sorted(zero, key=lambda r: -cost(r))[:WASTE_TOP_N]
    rep.add(S, "Wasted spend (06 G16)", f"{len(zero)} terms over {ev.currency} {WASTE_MIN_COST:.0f} with zero conversions total {num(zero_cost)}, {pct(share)} of the {num(visible)} visible. Top: "
            + "; ".join(f"\"{r['search_term_view.search_term']}\" {num(cost(r))} ({r['campaign.name']})" for r in top) + f". Source: {ev.link('exports/search_terms.csv')}.")
    rep.control("G16", "fail" if share > WASTE_SHARE_FAIL else "pass", f"{pct(share)} of visible term spend on zero-conversion terms")
    free = [r for r in terms if "free" in r["search_term_view.search_term"].lower()]
    if free:
        rep.add(S, "\"free\" intent", f"{len(free)} terms, {num(sum(cost(r) for r in free))}, {num(sum(conv(r) for r in free), 1)} conversions. Whether these are buyers depends on what a conversion is (see tracking).")
    if share > WASTE_SHARE_FAIL:
        rep.rec(S, "A fortnightly negative pass", Campaign="all enabled", Issue=f"{pct(share)} of visible term spend goes to terms that never convert (threshold {pct(WASTE_SHARE_FAIL, 0)}).",
                Evidence=f"{ev.link('exports/search_terms.csv')} (zero-conversion rows over {WASTE_MIN_COST:.0f})", Rule="06 G13, G16", Confidence="high",
                Change=f"Start with the {len(top)} top wasters above as phrase negatives where they are not wanted, then a fortnightly pass from gads pull (gads-manage). Keep informational terms that later convert.",
                Risk="over-negativing terms that convert later.", Impact=f"the share toward {pct(WASTE_SHARE_FAIL, 0)}.", Rollback="remove negatives.", Window="two cycles, 28 days.")
    kws = ev.export("keywords")
    if kws:
        agg = defaultdict(lambda: {"clicks": 0.0, "conv": 0.0, "cost": 0.0, "campaign": ""})
        for r in kws:
            k = (r["campaign.name"], r["ad_group_criterion.keyword.text"], r["ad_group_criterion.keyword.match_type"])
            agg[k]["clicks"] += io.parse_number(r.get("metrics.clicks")); agg[k]["conv"] += conv(r); agg[k]["cost"] += cost(r)
        waste = [(k, v) for k, v in agg.items() if v["clicks"] >= KEYWORD_WASTE_CLICKS and v["conv"] == 0]
        rep.control("G-WS1", "warning" if waste else "pass", f"{len(waste)} keywords over {KEYWORD_WASTE_CLICKS} clicks with no conversion")
        if waste:
            rep.add(S, "06 G-WS1", "; ".join(f"\"{k[1]}\" {k[2].lower()} in {k[0]} ({v['clicks']:.0f} clicks, {num(v['cost'])})" for k, v in waste[:5]) + f". Source: {ev.link('exports/keywords.csv')}.")
        broad = sum(1 for r in kws if r.get("ad_group_criterion.keyword.match_type") == "BROAD" and r.get("ad_group_criterion.status") == "ENABLED")
        rep.control("G17", "warning" if broad else "pass", f"{broad} enabled broad match keyword rows" if broad else "no broad match")
    else:
        rep.control("G-WS1", "no evidence", "no keywords.csv"); rep.control("G17", "no evidence", "no keywords.csv")
    rep.control("G18", "no evidence", "close variants are not separated in the export")

def rule_feed(rep, totals):
    ev, S = rep.ev, "feed"
    products = ev.export("products") or []
    feed = (ev.ws / "feed.tsv").exists() or (ev.ws / "feed.csv").exists()
    if not products and not feed:
        rep.add(S, "Status", "not run. No feed file in the workspace and no Shopping rows in the exports; the gads-feed skill and gads feedscore wait for a feed.")
        return
    rep.add(S, "Status", f"{len(products)} product rows in the window; " + ("a feed file is present, run gads feedscore and include feedscore.md here." if feed else "no feed file; export it from Merchant Center to run gads feedscore."))

def rule_roles(rep, totals):
    ev, S = rep.ev, "roles"
    if not totals:
        return
    settings = ev.deep("campaign_settings") or []
    st = {r["campaign.name"]: r for r in settings}
    crit = by_campaign(ev.deep("campaign_criteria"))
    W = {c["campaign"]: c for c in (ev.windows or {}).get("campaigns", [])}
    enabled = enabled_names(totals, settings)
    geo90 = by_campaign(ev.deep("geo_90d"))
    for name in enabled:
        c = totals.get(name, {})
        s = st.get(name, {})
        lines = []
        strategy = s.get("campaign.bidding_strategy_type") or c.get("strategy", "")
        target = ""
        if s:
            if s.get("campaign.maximize_conversions.target_cpa_micros") or s.get("campaign.target_cpa.target_cpa_micros"):
                target = f", tCPA {money(s.get('campaign.maximize_conversions.target_cpa_micros') or s.get('campaign.target_cpa.target_cpa_micros'))}"
            if s.get("campaign.maximize_conversion_value.target_roas") or s.get("campaign.target_roas.target_roas"):
                target = f", tROAS {s.get('campaign.maximize_conversion_value.target_roas') or s.get('campaign.target_roas.target_roas')}"
        lines.append(("Signal", f"{strategy}{target}; budget {money(s.get('campaign_budget.amount_micros') or c.get('budget'))} a day"
                      + (f"; primary status {s.get('campaign.primary_status')} ({', '.join(s.get('campaign.primary_status_reasons') or [])})" if s.get("campaign.primary_status") and s.get("campaign.primary_status") != "ELIGIBLE" else "")))
        locs = [geo_name(r["campaign_criterion.location.geo_target_constant"]) for r in crit.get(name, []) if r.get("campaign_criterion.type") == "LOCATION" and not r.get("campaign_criterion.negative")]
        if locs:
            lines.append(("Targets", ", ".join(locs) + (f"; partners {'on' if s.get('campaign.network_settings.target_partner_search_network') else 'off'}" if s else "")))
        elif not settings:
            lines.append(("Targets", "not visible without the deep pass"))
        if geo90.get(name):
            g = sorted(geo90[name], key=lambda r: -io.parse_number(r.get("metrics.cost_micros")))[:4]
            lines.append(("Spend by country (90 days)", ", ".join(f"{geo_name(r['geographic_view.country_criterion_id'])} {money(io.parse_number(r.get('metrics.cost_micros')))}" for r in g)))
        lines.append(("Window totals", f"cost {money(c.get('cost'))}, {num(c.get('conversions', 0), 1)} conversions, value {num(c.get('value', 0), 0)}, {roas(c['value'] / (c['cost'] / 1e6)) if c.get('cost') else 'n/a'}"))
        w = W.get(name)
        if w:
            ws = w["windows"]
            lines.append(("Windows read", "; ".join(f"{d}d {roas(ws[d]['cur']['roas']) if ws[d]['cur']['cost'] else 'no spend'}" + (f" (prior {roas(ws[d]['prior']['roas'])})" if ws[d].get('delta_roas') is not None else "") for d in ("7", "14", "30") if d in ws)
                          + f"; verdict {w['verdict']}; " + "; ".join(w.get("reasons", []))))
            lines.append(("Budget limited", ("yes" if w.get("budget_limited") else "no") + (f"; rank-lost impression share (7 days) {pct(w['rank_lost_7d'])}" if w.get("rank_lost_7d") is not None else "")))
            if w.get("verdict") == "scale":
                lines.append(("Step", w.get("step", "")))
        rep.campaigns.append((name, lines))
    _rule_structure(rep, totals, enabled, st, crit, W)

def _rule_structure(rep, totals, enabled, st, crit, W):
    ev, S = rep.ev, "roles"
    lk = lambda n: ev.link(ev.rel(ev.deep_dir / f"{n}.json")) if ev.deep(n) is not None else "the deep pass (not run)"
    # policy-limited ads
    pol = ev.deep("ad_policy_topics")
    if pol is not None:
        topics = defaultdict(set)
        for r in pol:
            for e in r.get("ad_group_ad.policy_summary.policy_topic_entries") or []:
                topics[e.get("topic", "unknown")].add(r["campaign.name"])
        if pol:
            rep.add(S, "Policy-limited ads", f"{len(pol)} ads not fully approved: " + "; ".join(f"{t} in {', '.join(sorted(c))}" for t, c in topics.items()) + f". Source: {lk('ad_policy_topics')}.")
            for t, camps in topics.items():
                rep.rec(S, f"Clear the {t} policy limit", Campaign=", ".join(sorted(camps)), Issue=f"ads limited by the {t} policy serve to a restricted set of auctions.",
                        Evidence=f"{lk('ad_policy_topics')}, {lk('ads')}", Rule="06 G29 and the policy itself", Confidence="high",
                        Change="Rewrite the flagged headlines and descriptions to comply (or file the policy exception with evidence), then request review.",
                        Risk="ad review takes one to three days per campaign.", Impact="the campaigns compete in every eligible auction.", Rollback="revert copy.", Window="14 days after approval.")
        else:
            rep.add(S, "Policy-limited ads", "none.")
    # ad strength
    ads = ev.deep("ads")
    if ads is not None:
        strength = defaultdict(int)
        for r in ads:
            strength[r.get("ad_group_ad.ad_strength", "UNKNOWN")] += 1
        poor = [r for r in ads if r.get("ad_group_ad.ad_strength") == "POOR"]
        rep.add(S, "Ads", f"{len(ads)} enabled RSAs: " + ", ".join(f"{n} {s.title()}" for s, n in sorted(strength.items(), key=lambda x: -x[1])) + f". Source: {lk('ads')}.")
        rep.control("G29", "fail" if poor else "pass", f"{len(poor)} Poor")
        per_group = defaultdict(int)
        for r in ads:
            per_group[(r["campaign.name"], r["ad_group.name"])] += 1
        rep.control("G26", "warning" if per_group and max(per_group.values()) == 1 else "pass", "one RSA per ad group" if per_group and max(per_group.values()) == 1 else "more than one RSA in some ad groups")
        if poor:
            rep.rec(S, "Rebuild the Poor-strength ads", Campaign=", ".join(sorted({r['campaign.name'] for r in poor})), Issue=f"{len(poor)} RSAs at Poor strength.",
                    Evidence=lk("ads"), Rule="06 G29", Confidence="high", Change="Rebuild each to Good or better with the ad group's keyword in two headlines and every headline distinct.",
                    Risk="low.", Impact="better auction eligibility and CTR.", Rollback="restore the old assets.", Window="14 days.")
    else:
        rep.control("G29", "no evidence", "ads need the deep pass"); rep.control("G26", "no evidence", "ads need the deep pass")
    # click strategies past the floor
    click = [n for n in enabled if (st.get(n, {}).get("campaign.bidding_strategy_type") or totals[n]["strategy"]) in CLICK_STRATEGIES]
    past = [n for n in click if totals[n]["conversions"] >= CLICK_STRATEGY_FLOOR]
    ecpc = [n for n in enabled if (st.get(n, {}).get("campaign.bidding_strategy_type") or totals[n]["strategy"]) == "ENHANCED_CPC"]
    rep.control("G36", "fail" if ecpc else ("warning" if past else "pass"), f"{len(click)} click-based campaigns, {len(past)} past the {CLICK_STRATEGY_FLOOR}-conversion floor" + (f"; ECPC on {', '.join(ecpc)}" if ecpc else ""))
    for n in past:
        w = W.get(n, {})
        rep.rec(S, f"{n} onto a strategy that can see money", Campaign=n, Issue=f"{money(totals[n]['cost'])} over the window on {st.get(n, {}).get('campaign.bidding_strategy_type') or totals[n]['strategy']} with {num(totals[n]['conversions'], 1)} conversions, past the point where 02 moves to a conversion strategy.",
                Evidence=f"{ev.link('exports/campaigns.csv')}" + (f", {lk('campaign_settings')}" if st else "") + (f", {ev.link(ev.calc('windows'))}" if w else ""),
                Rule="02 Bid Strategy Progression; 06 G36", Confidence="high",
                Change="After the tracking fix, Maximize Conversion Value with a tROAS a little above the campaign's own purchase ROAS for 30 days; until then a device bid adjustment where the device split warrants one.",
                Risk="volume drops while the strategy learns.", Impact="the spend stops buying clicks it cannot value.", Rollback="back to the click strategy.", Window="7, 14, 30 gate.")
    # negative lists
    sets = ev.deep("shared_sets")
    if sets is not None:
        lists = defaultdict(set)
        for r in sets:
            if r.get("shared_set.type") == "NEGATIVE_KEYWORDS":
                lists[(r["shared_set.name"], r.get("shared_set.member_count", 0))].add(r["campaign.name"])
        rep.add(S, "Negative lists", "; ".join(f"\"{n}\" ({m}) on {len(c)} of {len(enabled)}" for (n, m), c in lists.items()) + (f". Source: {lk('shared_sets')}." if lists else f"none attached. Source: {lk('shared_sets')}."))
        partial = [(n, m, sorted(set(enabled) - c)) for (n, m), c in lists.items() if set(enabled) - c and m >= 20]
        rep.control("G15", "warning" if partial else ("pass" if lists else "fail"), f"{len(partial)} large lists missing from some campaigns" if partial else ("lists on every campaign" if lists else "no negative lists"))
        rep.control("G14", "warning" if len(lists) < 3 else "pass", f"{len(lists)} negative lists (the checklist expects themed Competitor, Free and Generic lists)")
        for n, m, missing in partial:
            rep.rec(S, f"\"{n}\" on every campaign", Campaign=", ".join(missing), Issue=f"the {m}-term list \"{n}\" is missing from {len(missing)} of {len(enabled)} enabled campaigns.",
                    Evidence=lk("shared_sets"), Rule="06 G15", Confidence="high", Change=f"Attach \"{n}\" to {', '.join(missing)} after checking it holds nothing those campaigns want.",
                    Risk="low; review the list once.", Impact="the same protection on every campaign.", Rollback="detach.", Window="30 days.")
    else:
        rep.control("G15", "no evidence", "shared sets need the deep pass"); rep.control("G14", "no evidence", "shared sets need the deep pass")
    # audiences
    ca, aa, ul = ev.deep("campaign_audiences"), ev.deep("adgroup_audiences"), ev.deep("user_lists")
    if ca is not None and aa is not None:
        applied = len(ca) + len(aa)
        big = [u for u in (ul or []) if io.parse_number(u.get("user_list.size_for_search")) >= 1000]
        rep.add(S, "Audiences", f"{applied} applied at campaign or ad group level; {len(ul or [])} lists exist, {len(big)} with 1,000 or more members for search. Source: {lk('campaign_audiences')}, {lk('user_lists')}.")
        rep.control("G56", "fail" if applied == 0 and ul else "pass", f"{applied} applied")
        rep.control("G57", "pass" if ul else "warning", f"{len(ul or [])} lists exist")
        if applied == 0 and big:
            rep.rec(S, "Observation audiences on every campaign", Campaign="all enabled", Issue=f"no audiences applied while {len(ul)} lists exist ({len(big)} of a useful size).",
                    Evidence=f"{lk('campaign_audiences')}, {lk('adgroup_audiences')}, {lk('user_lists')}", Rule="06 G56, G57", Confidence="high",
                    Change="Add the owned lists (" + ", ".join(f"\"{u['user_list.name']}\"" for u in sorted(big, key=lambda u: -io.parse_number(u.get('user_list.size_for_search')))[:5]) + ") to every enabled campaign in observation mode; exclude past purchasers only where the catalogue has no repeat purchase.",
                    Risk="none in observation.", Impact="Smart Bidding gets warm-audience signal.", Rollback="remove.", Window="30 days.")
    else:
        rep.control("G56", "no evidence", "audiences need the deep pass"); rep.control("G57", "no evidence", "audiences need the deep pass")
    # partners, devices, geo overlap
    if st:
        off = [n for n in enabled if n in st and not st[n].get("campaign.network_settings.target_partner_search_network")]
        rep.control("G12", "warning" if len(off) == len(enabled) else "pass", f"Search Partners off on {len(off)} of {len(enabled)}")
        rep.control("G11", "pass" if all(st[n].get("campaign.geo_target_type_setting.positive_geo_target_type") == "PRESENCE" for n in enabled if n in st) else "warning", "geo type presence" if all(st[n].get("campaign.geo_target_type_setting.positive_geo_target_type") == "PRESENCE" for n in enabled if n in st) else "presence or interest on some campaigns")
        if off and len(off) == len(enabled):
            best = max(enabled, key=lambda n: totals[n]["conversions"])
            rep.rec(S, "Search Partners on one campaign", Campaign=best, Issue="Search Partners off everywhere.", Evidence=lk("campaign_settings"), Rule="06 G12", Confidence="low",
                    Change=f"Turn Search Partners on for {best} only, for 30 days, and read its CPA separately.", Risk="partner clicks at a worse conversion rate.", Impact="incremental reach.", Rollback="switch off.", Window="30 days.")
    else:
        rep.control("G12", "no evidence", "settings need the deep pass"); rep.control("G11", "no evidence", "settings need the deep pass")
    dev = by_campaign(ev.deep("device_90d"))
    if dev:
        mods = {n: {r["campaign_criterion.device.type"]: r.get("campaign_criterion.bid_modifier") for r in crit.get(n, []) if r.get("campaign_criterion.type") == "DEVICE"} for n in enabled}
        for n in enabled:
            d = {r["segments.device"]: r for r in dev.get(n, [])}
            desk, mob = d.get("DESKTOP"), d.get("MOBILE")
            if desk and mob:
                dc, mc = io.parse_number(desk.get("metrics.conversions")), io.parse_number(mob.get("metrics.conversions"))
                dcost, mcost = io.parse_number(desk.get("metrics.cost_micros")), io.parse_number(mob.get("metrics.cost_micros"))
                if dc >= DEVICE_MIN_CONV and mcost > 0:
                    d_cpa = dcost / dc; m_cpa = (mcost / mc) if mc else float("inf")
                    if m_cpa >= DEVICE_CPA_RATIO * d_cpa and not (mods.get(n, {}).get("MOBILE") or 0):
                        rep.add(S, f"Devices, {n}", f"desktop {money(dcost)} for {num(dc, 1)} conversions, mobile {money(mcost)} for {num(mc, 1)}; mobile CPA {'over ' + str(DEVICE_CPA_RATIO) + ' times' if mc else 'undefined'} desktop with no device modifier. Source: {lk('device_90d')}.")
                        rep.rec(S, f"Mobile bid adjustment on {n}", Campaign=n, Issue=f"mobile converts far worse than desktop ({num(mc, 1)} conversions on {money(mcost)} against {num(dc, 1)} on {money(dcost)}) with modifiers at zero.",
                                Evidence=f"{lk('device_90d')}, {lk('campaign_criteria')}", Rule="06 G58 (device performance)", Confidence="medium",
                                Change="A mobile bid adjustment of minus 30 to 40 percent while the campaign is on a click or CPA strategy; value bidding makes it unnecessary later.",
                                Risk="less mobile volume.", Impact="spend follows the converting device.", Rollback="reset to zero.", Window="14 days.")
    if crit:
        loc = {n: {geo_name(r["campaign_criterion.location.geo_target_constant"]) for r in crit.get(n, []) if r.get("campaign_criterion.type") == "LOCATION" and not r.get("campaign_criterion.negative")} for n in enabled}
        pairs = [(a, b, loc[a] & loc[b]) for i, a in enumerate(enabled) for b in enabled[i + 1:] if loc.get(a) and loc.get(b) and loc[a] & loc[b] and _same_product(a, b)]
        if pairs:
            rep.add(S, "Overlapping targets", "; ".join(f"{a} and {b} both target {', '.join(sorted(x))}" for a, b, x in pairs) + f". Source: {lk('campaign_criteria')}.")
            rep.control("G08", "fail", f"{len(pairs)} campaign pairs compete in the same auctions")
            for a, b, x in pairs:
                rep.rec(S, f"One auction per market for {a} and {b}", Campaign=f"{a}, {b}", Issue=f"both target {', '.join(sorted(x))} for the same product, so they bid against each other.",
                        Evidence=f"{lk('campaign_criteria')}, {lk('geo_90d')}", Rule="06 G01, G04, G08", Confidence="high",
                        Change="Retarget one to the market its name says, or pause it and let the other carry the shared location; never both on the same country.",
                        Risk="the paused one's conversions move to the other.", Impact="one auction per market, honest names.", Rollback="restore locations.", Window="30 days.")
        else:
            rep.control("G08", "pass", "no two enabled campaigns share a target for the same product")
    # keywords
    kq = ev.deep("keyword_quality_30d")
    if kq:
        scored = [r for r in kq if r.get("ad_group_criterion.quality_info.quality_score")]
        imp = sum(io.parse_number(r.get("metrics.impressions")) for r in scored)
        wqs = sum(io.parse_number(r.get("metrics.impressions")) * io.parse_number(r.get("ad_group_criterion.quality_info.quality_score")) for r in scored) / imp if imp else None
        low = [r for r in scored if io.parse_number(r.get("ad_group_criterion.quality_info.quality_score")) <= 3]
        rep.add(S, "Keywords", (f"{len(kq)} enabled keywords with impressions in 30 days, {len(scored)} scored, impression-weighted Quality Score {wqs:.1f}" if wqs is not None else f"{len(kq)} keywords, none scored") + (f"; {len(low)} at 3 or below" if low else "") + f". Source: {lk('keyword_quality_30d')}.")
        rep.control("G20", ("pass" if wqs >= QS_PASS else "warning") if wqs is not None else "no evidence", f"weighted QS {wqs:.1f}" if wqs is not None else "no scores")
        rep.control("G21", "warning" if low else "pass", f"{len(low)} keywords at 3 or below")
        rep.control("G-KW1", "warning" if len(scored) < len(kq) * 0.7 else "pass", f"{len(kq) - len(scored)} of {len(kq)} keywords unscored")
    else:
        for cid in ("G20", "G21", "G-KW1"):
            rep.control(cid, "no evidence", "keyword quality needs the deep pass")
    # landing pages
    lp = ev.deep("landing_pages_90d")
    if lp:
        tot = sum(io.parse_number(r.get("metrics.cost_micros")) for r in lp)
        home = [r for r in lp if re.match(r"^https?://[^/]+/?(\{|\?|$)", r.get("landing_page_view.unexpanded_final_url", ""))]
        hc = sum(io.parse_number(r.get("metrics.cost_micros")) for r in home)
        top = sorted(lp, key=lambda r: -io.parse_number(r.get("metrics.cost_micros")))[:3]
        rep.add(S, "Landing pages", "; ".join(f"{r['campaign.name']} to {r['landing_page_view.unexpanded_final_url'].split('?')[0][:80]} {money(io.parse_number(r.get('metrics.cost_micros')))} for {num(io.parse_number(r.get('metrics.conversions')), 1)}" for r in top)
                + (f". The homepage took {money(hc)} ({pct(hc / tot) if tot else 'n/a'})." if home else ". No spend lands on the homepage.") + f" Source: {lk('landing_pages_90d')}.")
        rep.headline["homepage_share"] = (hc / tot) if tot else 0
    # change events
    ce = ev.deep("change_events_28d")
    if ce is not None:
        cw = (ev.manifest or {}).get("windows", {}).get("changes", ["?", "?"])
        rep.add(S, f"Change history, {cw[0]} to {cw[1]}", (f"{len(ce)} change event{'s' if len(ce) != 1 else ''}; the last by {ce[0].get('change_event.user_email', '?')} on {str(ce[0].get('change_event.change_date_time', ''))[:10]} ({ce[0].get('change_event.change_resource_type', '')})." if ce else "no change events. Nobody has touched the account in four weeks.") + f" Source: {lk('change_events_28d')}.")
        rep.control("G13", "fail" if not ce else "pass", f"{len(ce)} changes in 28 days")
        rep.control("G-AD1", "fail" if not any(r.get("change_event.change_resource_type") in ("AD", "AD_GROUP_AD", "ASSET") for r in ce) else "pass", "ad changes in 28 days" if ce else "no changes")
    else:
        rep.control("G13", "no evidence", "change events need the deep pass"); rep.control("G-AD1", "no evidence", "change events need the deep pass")
    # target sanity
    if st and W:
        for n in enabled:
            s = st.get(n, {}); w = W.get(n, {})
            tcpa = io.parse_number(s.get("campaign.maximize_conversions.target_cpa_micros")) or io.parse_number(s.get("campaign.target_cpa.target_cpa_micros"))
            cpa30 = ((w.get("windows") or {}).get("30") or {}).get("cur", {}).get("cpa")
            if tcpa and cpa30:
                gap = abs(cpa30 - tcpa) / tcpa
                rep.control("G37", "pass" if gap <= TARGET_TOLERANCE else "warning", f"{n} tCPA {money(tcpa)} against a 30-day CPA of {money(cpa30)}" + ("" if gap <= TARGET_TOLERANCE else f" ({pct(gap, 0)} apart)"))
                break
    budget_limited = [n for n in enabled if W.get(n, {}).get("budget_limited")]
    rep.control("G39", "warning" if budget_limited else "pass", f"budget-limited: {', '.join(budget_limited)}" if budget_limited else "no campaign budget-limited in the last 7 days")
    # assets
    ca_, aga, cua = ev.deep("customer_assets"), ev.deep("adgroup_assets"), ev.deep("campaign_assets")
    if cua is not None and ca_ is not None:
        types = defaultdict(int)
        for r in (ca_ or []) + (cua or []) + (aga or []):
            types[r.get("customer_asset.field_type") or r.get("campaign_asset.field_type") or r.get("ad_group_asset.field_type") or "?"] += 1
        rep.add(S, "Assets", ", ".join(f"{n} {t.lower().replace('_', ' ')}" for t, n in sorted(types.items(), key=lambda x: -x[1])) + f". Source: {lk('customer_assets')}, {lk('campaign_assets')}, {lk('adgroup_assets')}.")
        for cid, t in (("G50", "SITELINK"), ("G51", "CALLOUT"), ("G52", "STRUCTURED_SNIPPET"), ("G53", "AD_IMAGE")):
            rep.control(cid, "pass" if types.get(t) else "warning", f"{types.get(t, 0)} {t.lower().replace('_', ' ')}")
    else:
        for cid in ("G50", "G51", "G52", "G53"):
            rep.control(cid, "no evidence", "assets need the deep pass")
    # naming
    names = [n for n in enabled]
    seps = {("|" in n) or ("_" in n) or (" I " in n) for n in names}
    rep.control("G01", "pass" if names and len(seps) == 1 and True in seps else ("warning" if names else "no evidence"), "one separator convention across the enabled campaigns" if names and len(seps) == 1 else "mixed conventions")

def _same_product(a, b):
    """Two campaign names share a product when they share a word of five or more letters that is not a region."""
    stop = {"training", "course", "courses", "search", "brand", "generic"}
    wa = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", a)} - stop
    wb = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", b)} - stop
    return bool(wa & wb)

# ---------------------------------------------------------------- reviewed additions

REVIEW_FILE = "audit-review.md"
REC_TOKEN = re.compile(r"\{rec:([^}]+)\}")

def load_review(run_dir):
    """runs/<date>/audit-review.md, the reviewer's file. Blocks start with a level-two heading:
    `## Recommendation - <title>` (fields as **Label:** lines; optional **Section:** tracking|leakage|pmax|
    misallocation|feed|roles and **After:** <generated title prefix>), `## Campaign - <name>` (labelled
    lines merged into that campaign's block; Job goes first, the rest after Signal), `## Override - <generated
    title prefix>` (fields that replace the draft's, or **Drop:** yes to remove it), `## Caveat` (labelled
    lines appended to Caveats). `{rec:<title prefix>}` anywhere resolves to that recommendation's number
    after numbering. Returns None when the file is absent."""
    p = Path(run_dir) / REVIEW_FILE
    if not p.exists():
        return None
    review = {"recs": [], "campaigns": defaultdict(list), "overrides": [], "caveats": [], "path": p}
    kind, name, fields = None, None, []
    def flush():
        if kind == "Recommendation":
            f = dict(fields)
            review["recs"].append({"title": name, "section": f.pop("Section", "roles"), "after": f.pop("After", None), "fields": f})
        elif kind == "Campaign":
            review["campaigns"][name].extend(fields)
        elif kind == "Override":
            review["overrides"].append({"title": name, "fields": dict(fields)})
        elif kind == "Caveat":
            review["caveats"].extend(fields)
    for line in p.read_text().splitlines():
        m = re.match(r"^## (Recommendation|Campaign|Override|Caveat)(?: - (.+))?$", line)
        if m:
            flush()
            kind, name, fields = m.group(1), (m.group(2) or "").strip(), []
            continue
        f = re.match(r"^\*\*([^*]+):\*\* ?(.*)$", line)
        if f and kind:
            fields.append((f.group(1).strip(), f.group(2).strip()))
        elif kind and fields and line.strip() and not line.startswith("#"):
            fields[-1] = (fields[-1][0], (fields[-1][1] + " " + line.strip()).strip())
    flush()
    return review

def apply_review(rep, review):
    """Overrides and drops first, then the reviewer's recommendations in position, then campaign lines and caveats."""
    if not review:
        return
    for o in review["overrides"]:
        target = next((r for r in rep.recs if r["title"].lower().startswith(o["title"].lower())), None)
        if not target:
            rep.review_notes.append(f"override for \"{o['title']}\" matched no drafted recommendation")
            continue
        if str(o["fields"].get("Drop", "")).lower() in ("yes", "true"):
            rep.recs.remove(target)
            rep.review_notes.append(f"dropped the draft \"{target['title']}\"")
            continue
        for k, v in o["fields"].items():
            if k in FIELD_ORDER or k == "title":
                target[k] = v
        target["reviewed"] = "edited"
    for r in review["recs"]:
        rec = {"section": r["section"], "title": r["title"], "reviewed": "added"}
        for k in FIELD_ORDER:
            rec[k] = r["fields"].get(k, "")
        rec["Owner"] = rec["Owner"] or OWNER
        rec["Approval"] = rec["Approval"] or DRAFT
        pos = len(rep.recs)
        if r["after"]:
            for i, x in enumerate(rep.recs):
                if x["title"].lower().startswith(r["after"].lower()):
                    pos = i + 1
                    break
        else:
            same = [i for i, x in enumerate(rep.recs) if x["section"] == r["section"]]
            pos = (same[-1] + 1) if same else len(rep.recs)
        rep.recs.insert(pos, rec)
    for name, lines in review["campaigns"].items():
        block = next((b for b in rep.campaigns if b[0] == name), None)
        if not block:
            rep.review_notes.append(f"campaign lines for \"{name}\" matched no enabled campaign")
            continue
        existing = block[1]
        first = [l for l in lines if l[0] == "Job"]
        rest = [l for l in lines if l[0] != "Job"]
        sig = next((i for i, (lab, _) in enumerate(existing) if lab == "Signal"), -1)
        for l in reversed(first):
            existing.insert(0, l)
        insert_at = (sig + 1 + len(first)) if sig >= 0 else len(existing)
        for l in reversed(rest):
            existing.insert(insert_at, l)
    rep.caveats.extend(review["caveats"])

def resolve_tokens(rep):
    """{rec:<title prefix>} -> the number of the first recommendation whose title starts with that text."""
    def sub(text):
        def repl(m):
            key = m.group(1).strip().lower()
            for r in rep.recs:
                if r["title"].lower().startswith(key):
                    return str(r["number"])
            rep.review_notes.append(f"{{rec:{m.group(1)}}} matched no recommendation")
            return m.group(0)
        return REC_TOKEN.sub(repl, text) if isinstance(text, str) else text
    for r in rep.recs:
        for k in FIELD_ORDER + ["title"]:
            r[k] = sub(r.get(k, ""))
    rep.campaigns = [(n, [(l, sub(t)) for l, t in lines]) for n, lines in rep.campaigns]
    rep.caveats = [(l, sub(t)) for l, t in rep.caveats]
    rep.sections = defaultdict(list, {k: [(l, sub(t)) for l, t in v] for k, v in rep.sections.items()})

# ---------------------------------------------------------------- composition

def build(ev):
    rep = Report(ev)
    totals = rule_overview(rep)
    rule_tracking(rep, totals)
    rule_leakage(rep, totals)
    rule_pmax(rep, totals)
    rule_misallocation(rep, totals)
    rule_feed(rep, totals)
    rule_roles(rep, totals)
    order = ["tracking", "leakage", "pmax", "misallocation", "feed", "roles"]
    rep.recs.sort(key=lambda r: order.index(r["section"]))
    rep.review = load_review(ev.run_dir)
    apply_review(rep, rep.review)
    rep.recs.sort(key=lambda r: order.index(r["section"]))
    for i, r in enumerate(rep.recs, 1):
        r["number"] = i
    resolve_tokens(rep)
    return rep

SECTION_TITLES = {"tracking": "1. Conversion tracking (audit 1.1)", "leakage": "2. Branded leakage (audit 1.2)", "pmax": "3. PMax constraint (audit 1.3)",
                  "misallocation": "4. Spend misallocation (audit 1.4)", "feed": "5. Merchant Center (audit 1.5)", "roles": "6. Campaign roles (audit 1.6)"}
SECTION_REFS = {"tracking": "06 G42 to G49 and G-CT1 to G-CT3, method 07, standard in 02 Measurement Standard", "leakage": "gads skill brand-bidding rule; 06 G05",
                "pmax": "02 PMax Rules and 06 G06, G07, G-PM1 to G-PM6", "misallocation": "06 G13 to G19", "feed": "03 Merchant Center standards", "roles": "06 G01 to G12, G20 to G61"}

def three_changes(rep):
    """The three recommendations that move new-customer ROAS most: tracking first, then bidding and ads on the biggest spender, then structure."""
    picks, seen = [], set()
    for pred in (lambda r: r["section"] == "tracking", lambda r: r["section"] == "roles" and "strategy" in r["title"], lambda r: r["section"] == "roles" and "policy" in r["title"].lower(),
                 lambda r: r["section"] in ("leakage", "roles", "misallocation")):
        for r in rep.recs:
            if pred(r) and r["number"] not in seen:
                picks.append(r); seen.add(r["number"])
                break
    for r in rep.recs:
        if len(picks) >= 3:
            break
        if r["number"] not in seen:
            picks.append(r); seen.add(r["number"])
    return picks[:3]

def render_audit(rep):
    ev = rep.ev
    L = []
    name = ev.data.get("customer_name", ev.data.get("customer_id", "the account"))
    L += [f"# Google Ads audit - {name} - {ev.run_date}", "",
          f"**Account:** {ev.data.get('customer_id', '?')}, currency {ev.currency or '?'}, time zone {ev.data.get('timezone', '?')}.", "",
          "**Kind:** read-only audit composed by `gads audit` from the files below; the recommendations are rule-drafted and marked draft until the account manager has reviewed them. Nothing in the account was changed.", "",
          f"**Written:** {date.today().isoformat()} by google-ads-playbook; run date {ev.run_date}" + (f", deep pass {ev.deep_dir.name}" if ev.deep_dir else ", no deep pass") + ".", "",
          "## Data used", ""]
    groups = [("Exports", [u for u in ev.used if u.startswith("exports/")]), ("Calculators and checks", [u for u in ev.used if u.startswith("runs/")]),
              ("Settings deep pass", [u for u in ev.used if u.startswith("raw/")])]
    for label, items in groups:
        if items:
            L += [f"**{label}:** " + ", ".join(ev.link(u) for u in items) + ".", ""]
    if ev.deep_dir:
        L += [f"**Deep pass windows:** " + "; ".join(f"{k} {v[0]} to {v[1]}" for k, v in (ev.manifest or {}).get("windows", {}).items()) + ".", ""]
    L += ["**Playbook references:** [02 architecture](https://github.com/juliandickie/google-ads-playbook/blob/main/references/02-google-ads-architecture.md), [06 audit checklist](https://github.com/juliandickie/google-ads-playbook/blob/main/references/06-google-audit-checklist.md), [07 conversion tracking](https://github.com/juliandickie/google-ads-playbook/blob/main/references/07-conversion-tracking-execution.md).", ""]
    if ev.missing:
        L += ["## Missing evidence", "", "Sources this run did not have and what would produce them. Every control they would have decided reads \"no evidence\" below.", ""]
        for src, why in ev.missing:
            L += [f"**{src}:** {why}.", ""]
    L += ["## What the data says before any recommendation", ""]
    for label, text in rep.sections.get("overview", []):
        L += [f"**{label}:** {text}", ""]
    for key in ("tracking", "leakage", "pmax", "misallocation", "feed", "roles"):
        L += [f"## {SECTION_TITLES[key]}", "", f"**Reference:** {SECTION_REFS[key]}.", ""]
        if key == "roles" and rep.campaigns:
            L += ["### Per campaign", ""]
            for cname, lines in rep.campaigns:
                L += [f"#### {cname}", ""]
                for label, text in lines:
                    L += [f"**{label}:** {text}", ""]
            L += ["### Flags", ""]
        elif rep.sections.get(key):
            L += ["### Findings", ""]
        for label, text in rep.sections.get(key, []):
            L += [f"**{label}:** {text}", ""]
        for r in [r for r in rep.recs if r["section"] == key]:
            L += [f"### Recommendation {r['number']} - {r['title']}", ""]
            for f in FIELD_ORDER:
                if r.get(f):
                    L += [f"**{f}:** {r[f]}", ""]
            if r.get("reviewed"):
                L += [f"**Reviewed:** {'added by the reviewer' if r['reviewed'] == 'added' else 'edited by the reviewer'} in {REVIEW_FILE}.", ""]
    L += ["## The three changes that move new-customer ROAS most, in order", ""]
    for i, r in enumerate(three_changes(rep), 1):
        L += [f"**{('First', 'Second', 'Third')[i - 1]}, recommendation {r['number']} ({r['title']}):** {r['Change']}", ""]
    L += ["## Checklist walk, 06 by section", ""]
    controls = parse_checklist()
    if controls:
        section = None
        for sec, cid, cname, sev in controls:
            if sec != section:
                section = sec
                L += [f"### {sec.split('(')[0].strip()}", ""]
            verdict, note = rep.controls.get(cid, ("no evidence", "not decidable from the files"))
            L += [f"**{cid} {cname}:** {verdict}" + (f" ({note})" if note else "") + ".", ""]
    else:
        for cid, (verdict, note) in sorted(rep.controls.items()):
            L += [f"**{cid}:** {verdict} ({note}).", ""]
    L += ["## Caveats", ""]
    for label, text in rep.caveats:
        L += [f"**{label}:** {text}", ""]
    if rep.review:
        added = [r for r in rep.recs if r.get("reviewed") == "added"]; edited = [r for r in rep.recs if r.get("reviewed") == "edited"]
        L += [f"**Reviewed:** {len(added)} recommendation{'s' if len(added) != 1 else ''} added and {len(edited)} edited from {ev.link(ev.rel(rep.review['path']))}; the generated drafts are the rest." + (" Could not place: " + "; ".join(rep.review_notes) + "." if rep.review_notes else ""), ""]
    L += ["**Drafts:** every recommendation not marked reviewed was drafted by rule from the files; the account manager reviews the judgement (the Change, Risk and Impact lines) before anything is applied or shown to the client. Review edits belong in " + REVIEW_FILE + ", never in this file, which every run rewrites.", ""]
    if ev.leakage:
        L += [f"**Floors:** {' '.join(ev.leakage.get('assumptions', []))}", ""]
    L += ["**Snapshot:** the settings and the SERP verdicts are reads on the run date; anything changed after that is not reflected.", ""]
    return "\n".join(L)

def render_executive(rep):
    """Two pages for the client owner. Client voice, no links, no internal notes."""
    ev = rep.ev
    h = rep.headline
    name = ev.data.get("customer_name", "your account")
    cur = ev.currency or ""
    L = [f"# Google Ads review - {name}", "", "## The headline", "",
         f"**As at {ev.run_date}:** a read-only review; nothing in the account has been changed.", ""]
    if h.get("cost") is not None:
        L += [f"**Over the window {h.get('window', '')}:** {cur} {money(h['cost'])} spent for {cur} {num(h['value'], 0)} in tracked value, a return of {roas(h.get('roas'))} on ad spend across {h.get('enabled', '?')} active campaigns.", ""]
    if h.get("roas_30") is not None:
        L += [f"**The last 30 days:** {roas(h['roas_30'])}" + (f", {'down' if h['delta_30'] < 0 else 'up'} {abs(h['delta_30']) * 100:.0f} percent on the 30 days before" if h.get("delta_30") is not None else "") + f", against a target of {h.get('target_roas')}x.", ""]
    if h.get("primary_90d"):
        L += [f"**What the bidding is chasing:** of the {num(h['primary_90d'], 0)} conversions the account optimises toward in the last 90 days, {num(h['non_purchase_primary_90d'], 0)} are not purchases. Until that changes, the return figures above describe an algorithm buying the cheapest signal it can count, not sales.", ""]
    if h.get("true_roas") is not None:
        L += [f"**New-customer return:** {roas(h['true_roas'])} once branded searches are stripped out, against a blended {roas(h.get('blended'))}. Brand searches make up {pct(h.get('branded_share') or 0)} of the non-brand revenue.", ""]
    L += ["## The three changes that matter most", ""]
    for i, r in enumerate(three_changes(rep), 1):
        first = re.split(r"[.;] ", r["Change"])[0].rstrip(".;") + "."
        L += [f"**{i}. {r['title']}.** {first} Expected effect: {r['Impact']}", ""]
    L += ["## What we need from you", ""]
    asks = []
    if any(r["section"] == "tracking" for r in rep.recs):
        asks.append(("Your go on the tracking changes", "they reset what a conversion means, and the next 30 days will look worse before they look better."))
    if not ev.reconciliation:
        asks.append(("Sales records", "access to the cart or CRM and the attribution tool for one month, so the advertising numbers can be checked against real orders."))
    if not (ev.ws / "brand-kit.md").exists():
        asks.append(("Thirty minutes", "the brand and offer interview, which the campaign copy and landing pages depend on."))
    asks.append(("The date of each change", "as it is applied, so the follow-up reads the account against it."))
    for label, text in asks:
        L += [f"**{label}:** {text}", ""]
    L += ["**What happens next:** tracking first, then bidding and ads on the biggest campaign, then structure and negatives; a follow-up read 30 days after the tracking change, and a monthly brand search check.", ""]
    L += ["> **What this does not measure.** " + " ".join([
        "Search terms cover only part of the spend, because Google hides low-volume queries, so the waste and brand figures are floors.",
        "Nothing here judges the offer, the pricing or the margin; those are yours.",
        "The settings were read on the run date, and the recommendations are drafts until your account manager has reviewed them with you."]), ""]
    return "\n".join(L)

def to_json(rep):
    return {"run_date": rep.ev.run_date, "customer_id": rep.ev.data.get("customer_id"), "deep": rep.ev.deep_dir.name if rep.ev.deep_dir else None,
            "used": rep.ev.used, "missing": [{"source": s, "why": w} for s, w in rep.ev.missing], "headline": rep.headline,
            "sections": {k: [{"label": l, "text": t} for l, t in v] for k, v in rep.sections.items()},
            "campaigns": [{"campaign": n, "lines": [{"label": l, "text": t} for l, t in ls]} for n, ls in rep.campaigns],
            "recommendations": rep.recs, "controls": {k: {"verdict": v, "note": n} for k, (v, n) in rep.controls.items()},
            "review": {"file": rep.ev.rel(rep.review["path"]) if rep.review else None, "notes": rep.review_notes, "caveats": [{"label": l, "text": t} for l, t in rep.caveats]}}

def run(ws, run_date=None, deep=None, executive=False):
    ev = Evidence(ws, run_date, deep)
    rep = build(ev)
    out = io.run_dir(ws, ev.run_date)
    (out / "audit.md").write_text(render_audit(rep) + "\n")
    (out / "audit.json").write_text(json.dumps(to_json(rep), indent=1, default=str) + "\n")
    if executive:
        (out / "audit-executive.md").write_text(render_executive(rep) + "\n")
    return rep, out

def cmd_audit(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    rep, out = run(ws, args.run_date, args.deep, args.executive)
    verdicts = defaultdict(int)
    for v, _ in rep.controls.values():
        verdicts[v] += 1
    print(f"audit: {len(rep.recs)} draft recommendations, controls " + ", ".join(f"{n} {v}" for v, n in sorted(verdicts.items(), key=lambda x: -x[1]))
          + f", {len(rep.ev.missing)} missing sources" + (f", review merged ({sum(1 for r in rep.recs if r.get('reviewed'))} reviewed)" if rep.review else "")
          + (f", UNPLACED: {'; '.join(rep.review_notes)}" if rep.review_notes else "") + f" -> {out / 'audit.md'}" + (f" and audit-executive.md" if args.executive else ""))
    return 0

def register(sub, add_common):
    p = sub.add_parser("audit", help="compose the audit report from the calculators, the deep pass and the exports (rule-drafted recommendations for the skill to review)")
    p.add_argument("--deep", help="the deep pass date to read (raw/deep-<date>), default the newest")
    p.add_argument("--executive", action="store_true", help="also write audit-executive.md, two pages for the client owner")
    add_common(p)
    p.set_defaults(func=cmd_audit)
