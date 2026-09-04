"""Canonical export schema. Column names are Google Ads API (GAQL) field names."""
METRICS = ["metrics.impressions", "metrics.clicks", "metrics.cost_micros", "metrics.conversions", "metrics.conversions_value"]

COLUMNS = {
    "campaigns": ["segments.date", "campaign.id", "campaign.name", "campaign.status", "campaign.advertising_channel_type",
                  "campaign.bidding_strategy_type", "campaign_budget.amount_micros"] + METRICS +
                 ["metrics.search_impression_share", "metrics.search_budget_lost_impression_share", "metrics.search_rank_lost_impression_share"],
    "ad_groups": ["campaign.id", "campaign.name", "ad_group.id", "ad_group.name", "ad_group.status"] + METRICS,
    "keywords": ["campaign.id", "campaign.name", "ad_group.id", "ad_group.name", "ad_group_criterion.criterion_id",
                 "ad_group_criterion.keyword.text", "ad_group_criterion.keyword.match_type", "ad_group_criterion.status",
                 "ad_group_criterion.quality_info.quality_score"] + METRICS,
    "search_terms": ["campaign.id", "campaign.name", "ad_group.id", "ad_group.name", "search_term_view.search_term",
                     "segments.search_term_match_type"] + METRICS,
    "products": ["campaign.id", "campaign.name", "segments.product_item_id", "segments.product_title", "segments.product_brand"] + METRICS,
    "conversion_actions": ["conversion_action.id", "conversion_action.name", "conversion_action.category", "conversion_action.type",
                           "conversion_action.status", "conversion_action.primary_for_goal", "conversion_action.counting_type",
                           "conversion_action.click_through_lookback_window_days", "conversion_action.view_through_lookback_window_days",
                           "conversion_action.attribution_model_settings.attribution_model", "conversion_action.include_in_conversions_metric",
                           "conversion_action.phone_call_duration_seconds", "conversion_action.value_settings.default_value"],
}
REPORT_TYPES = list(COLUMNS)
