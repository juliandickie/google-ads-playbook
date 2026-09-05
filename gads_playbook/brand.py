"""Brand-term detection and campaign classification (spec section 6.2)."""
import re
from . import io

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")
NONBRAND_MARKERS = ("non-brand", "nonbrand", "non brand", "non_brand", "generic")

def _clicks(v):
    """Non-numeric or blank clicks counts as 0 (T2): a UI export can show '--' for a suppressed
    low-volume row, which must not raise ValueError out of the keyword-composition weighting below."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

def normalise_text(s):
    s = _PUNCT.sub(" ", str(s or "").lower().replace("'", ""))
    return _WS.sub(" ", s).strip()

class Brand:
    def __init__(self, tokens):
        self.tokens = [normalise_text(t) for t in tokens if normalise_text(t)]
        # The collapsed (no-space) rule catches "iddacademy" for "iDD Academy". Applied to a short single
        # word it matches inside unrelated words ("idd" in "bidding"), so it is limited to multi-word tokens
        # and tokens of five or more characters; short tokens still match as whole words.
        self.collapsed = [t.replace(" ", "") for t in self.tokens if " " in t or len(t) >= 5]

    @classmethod
    def from_workspace(cls, data):
        tokens = data.get("brand_tokens") or []
        if not tokens:
            raise io.MissingInput("gads.json has no brand_tokens. Run gads setup to record the brand name and product lines.")
        return cls(tokens)

    def is_branded(self, term):
        t = normalise_text(term)
        if not t:
            return False
        words = " " + t + " "
        for tok in self.tokens:
            if " " + tok + " " in words:
                return True
        collapsed = t.replace(" ", "")
        return any(c and c in collapsed for c in self.collapsed)

    def classify_campaign(self, name, channel_type="", keyword_rows=None):
        n = normalise_text(name)
        is_pmax = (channel_type or "").upper() == "PERFORMANCE_MAX" or n.startswith("pmax") or "performance max" in n
        has_nonbrand = any(m.replace("-", " ").replace("_", " ") in n for m in NONBRAND_MARKERS)
        has_brand = ("brand" in n.split() or "branded" in n.split()) and not has_nonbrand
        if is_pmax:
            if "capture" in n or (has_brand and "excluded" not in n):
                return "pmax-capture"
            if "scaling" in n or has_nonbrand or "excluded" in n:
                return "pmax-scaling"
            return "pmax-unknown"
        if keyword_rows:
            has_campaign_key = any("campaign.name" in r for r in keyword_rows)
            rows = [r for r in keyword_rows if r.get("campaign.name") == name] if has_campaign_key else keyword_rows
            if rows:
                total = branded = 0.0
                for r in rows:
                    w = _clicks(r.get("metrics.clicks")) or 1.0
                    total += w
                    if self.is_branded(r.get("ad_group_criterion.keyword.text", "")):
                        branded += w
                if total:
                    return "brand" if branded / total > 0.5 else "nonbrand"
        if has_nonbrand:
            return "nonbrand"
        return "brand" if has_brand else "nonbrand"
