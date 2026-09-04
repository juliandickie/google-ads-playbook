"""GAQL queries for the canonical exports, and proto row flattening."""
from . import schema

def _select(cols):
    return "SELECT " + ", ".join(cols)

QUERIES = {
    "customer": "SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone FROM customer",
    "campaigns": _select(schema.COLUMNS["campaigns"]) + " FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}' AND campaign.status != 'REMOVED' ORDER BY segments.date",
    "ad_groups": _select(schema.COLUMNS["ad_groups"]) + " FROM ad_group WHERE segments.date BETWEEN '{start}' AND '{end}' AND ad_group.status != 'REMOVED'",
    "keywords": _select(schema.COLUMNS["keywords"]) + " FROM keyword_view WHERE segments.date BETWEEN '{start}' AND '{end}' AND ad_group_criterion.status != 'REMOVED'",
    "search_terms": _select(schema.COLUMNS["search_terms"]) + " FROM search_term_view WHERE segments.date BETWEEN '{start}' AND '{end}'",
    "products": _select(schema.COLUMNS["products"]) + " FROM shopping_performance_view WHERE segments.date BETWEEN '{start}' AND '{end}'",
    "conversion_actions": _select(schema.COLUMNS["conversion_actions"]) + " FROM conversion_action WHERE conversion_action.status != 'REMOVED'",
}

def render(name, start, end):
    return QUERIES[name].format(start=start, end=end)

def _value(v):
    if v is None:
        return ""
    if hasattr(v, "name") and not isinstance(v, str):
        return str(v.name)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)

def flatten(row, fields):
    out = {}
    for f in fields:
        cur = row
        ok = True
        for part in f.split("."):
            if cur is None or not hasattr(cur, part):
                ok = False
                break
            cur = getattr(cur, part)
        out[f] = _value(cur) if ok else ""
    return out
