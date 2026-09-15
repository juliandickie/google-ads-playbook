"""The settings deep pass behind `gads pull --deep`: the account state the six exports do not carry
(campaign settings and criteria, negatives, ads and policy topics, assets, audiences, conversion goals
and per-action volumes, quality components, landing pages, device and geo splits, change events).
One JSON file per query under raw/deep-<date>/, plus manifest.json. Read-only, search_stream only.

Unlike pull (two-phase, all or nothing), every query here is independent evidence, so a failure writes
<name>.error.txt beside the others and the pass carries on; the manifest and the stdout line name it."""
import enum, json
from datetime import date, timedelta
from pathlib import Path
from . import io
from .pull import make_client, _window_end

METRIC_DAYS = 90    # device, geo, landing page, conversion action volumes
QUALITY_DAYS = 30   # keyword quality components
CHANGE_DAYS = 28    # change_event refuses a start older than 30 days; 28 leaves the API a margin

ENABLED = "campaign.status = 'ENABLED'"
AUDIENCE_TYPES = "('USER_LIST', 'USER_INTEREST', 'CUSTOM_AUDIENCE', 'COMBINED_AUDIENCE', 'AUDIENCE')"

# name -> GAQL. Placeholders: {end} (yesterday in the account time zone), {m_start} (90-day metric
# window start), {q_start} (30-day quality window start), {c_start} and {c_end} (change window, the
# latter today so a change made this morning is visible).
QUERIES = {
    "customer": (
        "SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone, "
        "customer.auto_tagging_enabled, customer.optimization_score, "
        "customer.conversion_tracking_setting.conversion_tracking_status, "
        "customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled, "
        "customer.conversion_tracking_setting.google_ads_conversion_customer, "
        "customer.conversion_tracking_setting.conversion_tracking_id FROM customer"),
    "campaign_settings": (
        "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, "
        "campaign.bidding_strategy_type, campaign.bidding_strategy, "
        "campaign.network_settings.target_search_network, campaign.network_settings.target_content_network, "
        "campaign.network_settings.target_partner_search_network, "
        "campaign.geo_target_type_setting.positive_geo_target_type, campaign.geo_target_type_setting.negative_geo_target_type, "
        "campaign.target_cpa.target_cpa_micros, campaign.maximize_conversions.target_cpa_micros, "
        "campaign.target_roas.target_roas, campaign.maximize_conversion_value.target_roas, "
        "campaign_budget.amount_micros, campaign.serving_status, campaign.primary_status, "
        "campaign.primary_status_reasons, campaign.ad_serving_optimization_status "
        "FROM campaign WHERE campaign.status IN ('ENABLED', 'PAUSED') ORDER BY campaign.status, campaign.name"),
    "campaign_criteria": (
        "SELECT campaign.name, campaign.status, campaign_criterion.type, campaign_criterion.negative, "
        "campaign_criterion.location.geo_target_constant, campaign_criterion.keyword.text, "
        "campaign_criterion.keyword.match_type, campaign_criterion.ad_schedule.day_of_week, "
        "campaign_criterion.ad_schedule.start_hour, campaign_criterion.ad_schedule.end_hour, "
        "campaign_criterion.language.language_constant, campaign_criterion.device.type, campaign_criterion.bid_modifier "
        f"FROM campaign_criterion WHERE {ENABLED} AND campaign_criterion.status != 'REMOVED'"),
    "campaign_labels": (
        f"SELECT campaign.name, campaign.status, label.name FROM campaign_label WHERE {ENABLED}"),
    "shared_sets": (
        "SELECT campaign.name, campaign.status, shared_set.name, shared_set.type, shared_set.status, shared_set.member_count, "
        f"campaign_shared_set.status FROM campaign_shared_set WHERE {ENABLED} AND campaign_shared_set.status != 'REMOVED'"),
    "shared_criteria": (
        "SELECT shared_set.name, shared_set.type, shared_criterion.keyword.text, shared_criterion.keyword.match_type "
        "FROM shared_criterion WHERE shared_set.status = 'ENABLED'"),
    "adgroup_negatives": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type "
        f"FROM ad_group_criterion WHERE ad_group_criterion.negative = TRUE AND {ENABLED} AND ad_group_criterion.status != 'REMOVED'"),
    "ads": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, ad_group_ad.ad.id, ad_group_ad.status, ad_group_ad.ad.type, "
        "ad_group_ad.ad_strength, ad_group_ad.ad.final_urls, ad_group_ad.ad.responsive_search_ad.headlines, "
        "ad_group_ad.ad.responsive_search_ad.descriptions, ad_group_ad.policy_summary.approval_status, "
        "ad_group_ad.policy_summary.review_status "
        f"FROM ad_group_ad WHERE {ENABLED} AND ad_group.status = 'ENABLED' AND ad_group_ad.status = 'ENABLED'"),
    "ad_policy_topics": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group_ad.ad.id, ad_group_ad.policy_summary.approval_status, "
        "ad_group_ad.policy_summary.policy_topic_entries "
        f"FROM ad_group_ad WHERE {ENABLED} AND ad_group_ad.status = 'ENABLED' "
        "AND ad_group_ad.policy_summary.approval_status != 'APPROVED'"),
    "campaign_assets": (
        "SELECT campaign.name, campaign.status, campaign_asset.field_type, campaign_asset.status, campaign_asset.source, "
        f"asset.type, asset.name FROM campaign_asset WHERE {ENABLED} AND campaign_asset.status != 'REMOVED'"),
    "adgroup_assets": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group_asset.field_type, ad_group_asset.status, "
        f"asset.type, asset.name FROM ad_group_asset WHERE {ENABLED} AND ad_group_asset.status != 'REMOVED'"),
    "customer_assets": (
        "SELECT customer_asset.field_type, customer_asset.status, asset.type, asset.name "
        "FROM customer_asset WHERE customer_asset.status != 'REMOVED'"),
    "campaign_audiences": (
        "SELECT campaign.name, campaign.status, campaign_criterion.type, campaign_criterion.user_list.user_list, "
        "campaign_criterion.bid_modifier, campaign_criterion.negative "
        f"FROM campaign_criterion WHERE campaign_criterion.type IN {AUDIENCE_TYPES} AND {ENABLED} "
        "AND campaign_criterion.status != 'REMOVED'"),
    "adgroup_audiences": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group_criterion.type, ad_group_criterion.user_list.user_list, "
        "ad_group_criterion.audience.audience, ad_group_criterion.bid_modifier, ad_group_criterion.negative "
        f"FROM ad_group_criterion WHERE ad_group_criterion.type IN {AUDIENCE_TYPES} AND {ENABLED} "
        "AND ad_group_criterion.status != 'REMOVED'"),
    "user_lists": (
        "SELECT user_list.id, user_list.name, user_list.type, user_list.size_for_search, user_list.membership_status, "
        "user_list.size_range_for_search FROM user_list"),
    "customer_conversion_goals": (
        "SELECT customer_conversion_goal.category, customer_conversion_goal.origin, customer_conversion_goal.biddable "
        "FROM customer_conversion_goal"),
    "campaign_conversion_goals": (
        "SELECT campaign.name, campaign.status, campaign_conversion_goal.category, campaign_conversion_goal.origin, "
        f"campaign_conversion_goal.biddable FROM campaign_conversion_goal WHERE {ENABLED}"),
    "conversion_actions_full": (
        "SELECT conversion_action.id, conversion_action.name, conversion_action.origin, conversion_action.type, "
        "conversion_action.category, conversion_action.status, conversion_action.primary_for_goal, "
        "conversion_action.counting_type, conversion_action.include_in_conversions_metric, "
        "conversion_action.attribution_model_settings.attribution_model, "
        "conversion_action.click_through_lookback_window_days, conversion_action.view_through_lookback_window_days, "
        "conversion_action.value_settings.default_value, conversion_action.value_settings.always_use_default_value "
        "FROM conversion_action WHERE conversion_action.status = 'ENABLED'"),
    "conversion_action_metrics_90d": (
        "SELECT conversion_action.id, conversion_action.name, conversion_action.category, conversion_action.status, "
        "conversion_action.primary_for_goal, metrics.all_conversions, metrics.all_conversions_value "
        "FROM conversion_action WHERE segments.date BETWEEN '{m_start}' AND '{end}'"),
    "campaign_conversion_split_90d": (
        "SELECT campaign.name, campaign.status, segments.conversion_action_name, segments.conversion_action_category, "
        "metrics.conversions, metrics.conversions_value, metrics.all_conversions, metrics.all_conversions_value "
        f"FROM campaign WHERE segments.date BETWEEN '{{m_start}}' AND '{{end}}' AND {ENABLED}"),
    "keyword_quality_30d": (
        "SELECT campaign.name, campaign.status, ad_group.name, ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.quality_info.quality_score, "
        "ad_group_criterion.quality_info.creative_quality_score, ad_group_criterion.quality_info.post_click_quality_score, "
        "ad_group_criterion.quality_info.search_predicted_ctr, metrics.impressions, metrics.clicks, metrics.cost_micros, "
        "metrics.conversions "
        f"FROM keyword_view WHERE segments.date BETWEEN '{{q_start}}' AND '{{end}}' AND {ENABLED} "
        "AND ad_group_criterion.status = 'ENABLED' AND metrics.impressions > 0"),
    "device_90d": (
        "SELECT campaign.name, campaign.status, segments.device, metrics.clicks, metrics.cost_micros, metrics.conversions, "
        f"metrics.conversions_value FROM campaign WHERE segments.date BETWEEN '{{m_start}}' AND '{{end}}' AND {ENABLED}"),
    "geo_90d": (
        "SELECT campaign.name, campaign.status, geographic_view.country_criterion_id, geographic_view.location_type, metrics.clicks, "
        "metrics.cost_micros, metrics.conversions, metrics.conversions_value "
        f"FROM geographic_view WHERE segments.date BETWEEN '{{m_start}}' AND '{{end}}' AND {ENABLED} "
        "AND geographic_view.location_type = 'LOCATION_OF_PRESENCE'"),
    "landing_pages_90d": (
        "SELECT campaign.name, campaign.status, landing_page_view.unexpanded_final_url, metrics.clicks, metrics.cost_micros, "
        "metrics.conversions, metrics.conversions_value "
        f"FROM landing_page_view WHERE segments.date BETWEEN '{{m_start}}' AND '{{end}}' AND {ENABLED}"),
    "change_events_28d": (
        "SELECT change_event.change_date_time, change_event.change_resource_type, change_event.resource_change_operation, "
        "change_event.changed_fields, change_event.user_email, change_event.client_type, change_event.campaign, "
        "change_event.ad_group FROM change_event "
        "WHERE change_event.change_date_time BETWEEN '{c_start} 00:00:00' AND '{c_end} 23:59:59' "
        "ORDER BY change_event.change_date_time DESC LIMIT 10000"),
}

def windows(end):
    """The four window edges for one pull, from the window end (yesterday in the account zone)."""
    return {"end": end.isoformat(),
            "m_start": (end - timedelta(days=METRIC_DAYS - 1)).isoformat(),
            "q_start": (end - timedelta(days=QUALITY_DAYS - 1)).isoformat(),
            "c_start": (end + timedelta(days=1) - timedelta(days=CHANGE_DAYS - 1)).isoformat(),
            "c_end": (end + timedelta(days=1)).isoformat()}

def render(name, end):
    return QUERIES[name].format(**windows(end))

def select_fields(query):
    return [f.strip() for f in query.split("FROM")[0].strip()[len("SELECT"):].split(",")]

def to_json(v):
    """A proto value as plain JSON: enums by name (checked before int, proto-plus enums are IntEnums),
    messages as nested dicts, repeated fields as lists, primitives as themselves."""
    if isinstance(v, enum.Enum):
        return v.name
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    if hasattr(type(v), "to_dict"):  # proto-plus message
        return type(v).to_dict(v, use_integers_for_enums=False)
    if hasattr(v, "DESCRIPTOR"):  # raw protobuf message (FieldMask and other well-known types)
        from google.protobuf.json_format import MessageToDict
        return MessageToDict(v)
    if hasattr(v, "__iter__"):
        return [to_json(x) for x in v]
    return str(v)

def flatten(row, fields):
    """Flat dotted keys like gaql.flatten, but values stay native JSON (None when the path is absent)."""
    out = {}
    for f in fields:
        cur = row
        ok = True
        for part in f.split("."):
            if cur is None or not hasattr(cur, part):
                ok = False
                break
            cur = getattr(cur, part)
        out[f] = to_json(cur) if ok else None
    return out

def _raw_rows(client, customer_id, query):
    svc = client.get_service("GoogleAdsService")
    rows = []
    for batch in svc.search_stream(customer_id=customer_id, query=query):
        rows.extend(batch.results)
    return rows

def run(customer_id, ws, run_date=None, client=None, names=None):
    """Run every query in QUERIES (or the given names) and write raw/deep-<run_date>/<name>.json each,
    <name>.error.txt for a query the API rejects, and manifest.json. Returns the manifest dict."""
    ws = Path(ws)
    client = client or make_client()
    names = list(names or QUERIES)
    end, window_note = _window_end(_timezone(client, customer_id))
    w = windows(end)
    day = run_date or date.today().isoformat()
    out_dir = ws / "raw" / f"deep-{day}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"customer_id": customer_id, "run_date": day, "window_end": w["end"],
                "windows": {"metrics": [w["m_start"], w["end"]], "quality": [w["q_start"], w["end"]],
                            "changes": [w["c_start"], w["c_end"]]},
                "queries": {}}
    if window_note:
        manifest["window_note"] = window_note
    for name in names:
        query = QUERIES[name].format(**w)
        entry = {"gaql": query, "file": f"{name}.json", "rows": None, "error": None}
        for stale in (out_dir / f"{name}.json", out_dir / f"{name}.error.txt"):  # a rerun on the same date replaces both outcomes
            stale.unlink(missing_ok=True)
        try:
            rows = [flatten(r, select_fields(query)) for r in _raw_rows(client, customer_id, query)]
        except Exception as e:  # GoogleAdsException, transport, or auth error from the API client
            entry["error"] = str(e)
            entry["file"] = f"{name}.error.txt"
            (out_dir / entry["file"]).write_text(f"{query}\n\n{e}\n")
        else:
            entry["rows"] = len(rows)
            (out_dir / entry["file"]).write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        manifest["queries"][name] = entry
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest

def _timezone(client, customer_id):
    rows = _raw_rows(client, customer_id, "SELECT customer.time_zone FROM customer")
    if not rows:
        raise io.MissingInput(f"customer {customer_id} returned no customer row for the deep pass.")
    return rows[0].customer.time_zone

def summary(manifest, ws):
    q = manifest["queries"]
    failed = [n for n, e in q.items() if e["error"]]
    line = f"deep: {len(q)} queries, {len(q) - len(failed)} ok"
    if failed:
        line += f", {len(failed)} failed ({', '.join(failed)})"
    return line + f" -> {Path(ws) / 'raw' / ('deep-' + manifest['run_date'])}", failed
