"""Pull the canonical exports from the Google Ads API (spec section 6.8). Read-only, search_stream only, no writes to any account."""
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from . import io, schema, gaql
from .auth import CONFIG_DIR

CAUSES = ("the developer token's access level (test-account-only tokens cannot read production accounts, request Basic or "
          "Explorer access in the API Center), and the login customer id (the MCC must manage the target account, and "
          "login_customer_id in google-ads.yaml must be the MCC)")

IMPRESSION_SHARE_FIELDS = ("metrics.search_impression_share", "metrics.search_budget_lost_impression_share",
                           "metrics.search_rank_lost_impression_share")
# No empty-channel case here (unlike leakage.SEARCH_LIKE_CHANNELS): every row from the API carries a
# real campaign.advertising_channel_type, so there is nothing to default it against.
IMPRESSION_SHARE_CHANNELS = ("SEARCH", "SHOPPING")

def _window_end(tz_name):
    """Yesterday in the account's own time zone (ruling R37), so a pull run just after midnight in a
    zone west of the runner does not window in a day that has not finished there yet. An empty or
    unknown zone falls back to the local date and returns a note naming the fallback."""
    try:
        if not tz_name:
            raise ZoneInfoNotFoundError(tz_name)
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).date() - timedelta(days=1), None
    except ZoneInfoNotFoundError:
        return date.today() - timedelta(days=1), "account time zone unknown; window ended on the local date"

def make_client():
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError as e:
        raise io.MissingInput(
            "the google-ads client is not installed in this interpreter. gads re-execs auth, accounts, and pull under uv "
            "automatically unless GADS_IN_UV is set; if you are seeing this with GADS_IN_UV unset, install uv "
            "(brew install uv); if it is set on purpose, install the google-ads package in this interpreter yourself."
        ) from e
    yaml = CONFIG_DIR / "google-ads.yaml"
    if not yaml.exists():
        raise io.MissingInput(f"{yaml} not found. Run gads auth first.")
    try:
        return GoogleAdsClient.load_from_storage(str(yaml))
    except Exception as e:
        raise io.MissingInput(f"failed to load {yaml}: {e}") from e

def _resource_of(query):
    return query.split("FROM")[1].split()[0]

def api_error(query, e):
    resource = _resource_of(query)
    return io.MissingInput(f"the {resource} query failed: {e}. Likely causes: {CAUSES}.")

def _rows(client, customer_id, query, fields):
    svc = client.get_service("GoogleAdsService")
    try:
        batches = list(svc.search_stream(customer_id=customer_id, query=query))
    except Exception as e:  # GoogleAdsException, transport, or auth error from the API client
        raise api_error(query, e) from e
    out = []
    for batch in batches:
        for row in batch.results:
            out.append(gaql.flatten(row, fields))
    return out

def run(customer_id, login_customer_id, days, search_terms_days, ws, client=None):
    """Two-phase (ruling R25). Phase one reads the customer row and every report in schema.REPORT_TYPES order, holding
    all rows in memory; any API failure raises io.MissingInput and nothing is written. Phase two writes the six CSVs
    and then updates gads.json. The window end is yesterday in the account's own time zone (ruling R37)."""
    ws = Path(ws)
    client = client or make_client()

    cust = _rows(client, customer_id, gaql.render("customer", "", ""),
                 ["customer.currency_code", "customer.time_zone", "customer.descriptive_name"])
    if not cust:
        raise io.MissingInput(f"customer {customer_id} returned no customer row. Check the id and that {login_customer_id} manages it.")

    end, window_note = _window_end(cust[0].get("customer.time_zone", ""))
    start = end - timedelta(days=days - 1)
    st_start = end - timedelta(days=search_terms_days - 1)

    results = {}
    for name in schema.REPORT_TYPES:
        s = st_start if name == "search_terms" else start
        query = gaql.render(name, s.isoformat(), end.isoformat())
        rows = _rows(client, customer_id, query, schema.COLUMNS[name])
        if name == "campaigns":
            for row in rows:
                if row.get("campaign.advertising_channel_type") not in IMPRESSION_SHARE_CHANNELS:
                    for f in IMPRESSION_SHARE_FIELDS:
                        row[f] = ""
        results[name] = rows

    counts = {}
    for name in schema.REPORT_TYPES:
        rows = results[name]
        io.write_csv(ws / "exports" / f"{name}.csv", rows, schema.COLUMNS[name])
        counts[name] = len(rows)

    try:
        data = io.load_workspace(ws)
    except io.MissingInput:
        data = {}
    data.update({"customer_id": customer_id, "login_customer_id": login_customer_id, "customer_name": cust[0]["customer.descriptive_name"],
                 "currency": cust[0]["customer.currency_code"], "timezone": cust[0]["customer.time_zone"],
                 "window_start": start.isoformat(), "window_end": end.isoformat(), "search_terms_window_start": st_start.isoformat(),
                 "pulled_at": date.today().isoformat()})
    if window_note:
        data["window_note"] = window_note
    else:
        data.pop("window_note", None)
    io.save_workspace(ws, data)
    return counts

def cmd_pull(args):
    from .cli import workspace_from
    ws = workspace_from(args) if (args.workspace or os.environ.get("GADS_WORKSPACE")) else Path.home() / "gads" / args.customer.replace("-", "")
    search_terms_days = args.search_terms_days if args.search_terms_days is not None else args.days
    counts = run(args.customer.replace("-", ""), args.login_customer.replace("-", ""), args.days, search_terms_days, ws)
    print("pull: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f" -> {ws / 'exports'}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("pull", help="pull the canonical exports from the Google Ads API into the workspace")
    p.add_argument("--customer", required=True, help="client account id, digits only")
    p.add_argument("--login-customer", required=True, help="manager (MCC) id, digits only")
    p.add_argument("--days", type=int, default=180, help="campaign window in days ending yesterday in the account time zone (default 180)")
    p.add_argument("--search-terms-days", type=int, default=None, help="search terms window in days; defaults to --days so leakage and misallocate read one window")
    add_common(p)
    p.set_defaults(func=cmd_pull)
