"""Merchant Center feed completeness score, ten points per product (spec section 6.5)."""
import json
from pathlib import Path
from . import io, render

POINTS = ["title", "description", "images", "category", "product_type", "gtin", "sale pricing", "reviews", "shipping", "custom labels"]

def _has(row, key):
    return bool((row.get(key) or "").strip())

def score_product(row, brand_hint="", reviews=None, min_description=500):
    title = (row.get("title") or "").strip()
    brand = (row.get("brand") or brand_hint or "").strip().lower()
    checks = {
        "title": 70 <= len(title) <= 150 and (not brand or brand in title.lower()),
        "description": len((row.get("description") or "").strip()) >= min_description,
        "images": _has(row, "image_link") and _has(row, "additional_image_link"),
        "category": _has(row, "google_product_category") and ((row["google_product_category"].strip().isdigit()) or row["google_product_category"].count(">") >= 2),
        "product_type": _has(row, "product_type"),
        "gtin": _has(row, "gtin"),
        "sale pricing": (not _has(row, "sale_price")) or (_has(row, "sale_price") and _has(row, "sale_price_effective_date")),
        "reviews": bool(reviews) if reviews is not None else False,
        "shipping": _has(row, "shipping") or _has(row, "shipping_weight"),
        "custom labels": _has(row, "custom_label_0") and _has(row, "custom_label_1"),
    }
    missing = []
    for p in POINTS:
        if not checks[p]:
            if p == "reviews" and reviews is None:
                missing.append("reviews (unknown, pass --reviews-integrated)")
            elif p == "title":
                missing.append(f"title ({len(title)} chars{'' if not brand or brand in title.lower() else ', brand missing'})")
            elif p == "description":
                missing.append(f"description ({len((row.get('description') or '').strip())} chars, need {min_description})")
            else:
                missing.append(p)
    return sum(1 for p in POINTS if checks[p]), missing, checks

def compute(feed_rows, product_rows=None, reviews=None, min_description=500, top_n=10, brand_hint=""):
    revenue = {}
    for r in product_rows or []:
        pid = r.get("segments.product_item_id", "")
        revenue[pid] = revenue.get(pid, 0.0) + float(r.get("metrics.conversions_value") or 0)
    ranked_ids = [pid for pid, _ in sorted(revenue.items(), key=lambda kv: -kv[1])[:top_n]] if revenue else []
    out = []
    for row in feed_rows:
        pid = row.get("id", "")
        score, missing, checks = score_product(row, brand_hint, reviews, min_description)
        out.append({"id": pid, "title": row.get("title", ""), "score": score, "missing": missing, "revenue": revenue.get(pid, 0.0), "ranked": pid in ranked_ids})
    out.sort(key=lambda p: (not p["ranked"], -p["revenue"], p["score"]))
    rebuild = [p["id"] for p in out if p["score"] < 7]
    feed_ids = {row.get("id", "") for row in feed_rows}
    missing_from_feed = [pid for pid, _ in sorted(revenue.items(), key=lambda kv: -kv[1]) if pid and pid not in feed_ids]
    missing_from_feed_revenue = {pid: revenue[pid] for pid in missing_from_feed}
    return {"products": out, "rebuild": rebuild, "scored": len(out), "reviews_state": "unknown" if reviews is None else ("yes" if reviews else "no"),
            "min_description": min_description, "top_n": top_n,
            "missing_from_feed": missing_from_feed, "missing_from_feed_revenue": missing_from_feed_revenue}

def render_md(result):
    products = result["products"]
    top_n = result["top_n"]
    ranked_shown = [p for p in products if p["ranked"]][:top_n]
    ranked_shown_ids = {p["id"] for p in ranked_shown}
    remaining = [p for p in products if p["id"] not in ranked_shown_ids]
    lowest_shown = sorted(remaining, key=lambda p: p["score"])[:top_n]
    shown = ranked_shown + lowest_shown
    rows = [{"id": p["id"], "title": p["title"][:60], "score": f"{p['score']}/10", "rank": "top" if p["ranked"] else "", "missing": ", ".join(p["missing"])} for p in shown]
    dist = {}
    for p in products:
        dist[p["score"]] = dist.get(p["score"], 0) + 1
    dist_str = ", ".join(f"{s}: {dist.get(s, 0)}" for s in range(10, -1, -1) if dist.get(s, 0))
    lines = ["# Feed completeness score", "",
             f"{result['scored']} products scored. Reviews integrated: {result['reviews_state']}. Description floor {result['min_description']} characters (the standard is fill toward 5,000).",
             f"Score distribution: {dist_str or 'none'}. {len(result['rebuild'])} products need a rebuild (score under 7).", "",
             render.table(rows, ["id", "title", "score", "rank", "missing"], ["Item ID", "Title", "Score", "Revenue rank", "Missing points"]), "",
             "## Rebuild candidates (under 7)", ""]
    rebuild_shown = result["rebuild"][:top_n]
    lines += [f"- {pid}" for pid in rebuild_shown] or ["- None."]
    if len(result["rebuild"]) > top_n:
        lines.append(f"- and {len(result['rebuild']) - top_n} more in feedscore.json")
    lines += ["", "Run prompt 2.6 (Merchant Center rebuild) on each candidate with its missing points listed above."]
    missing_feed = result.get("missing_from_feed", [])
    mf_revenue = result.get("missing_from_feed_revenue", {})
    lines += ["", "## In products.csv but not in the feed", ""]
    if missing_feed:
        lines += [f"- {pid} ({mf_revenue.get(pid, 0):,.0f} revenue)" for pid in missing_feed]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"

def cmd_feedscore(args):
    from .cli import workspace_from
    ws = workspace_from(args)
    data = io.load_workspace(ws)
    feed = None
    for name in ("feed.tsv", "feed.csv", "feed.txt"):
        if (ws / name).exists():
            feed = ws / name
            break
    if args.feed:
        feed = Path(args.feed).expanduser()
    if not feed or not feed.exists():
        raise io.MissingInput("no feed file. Drop the Merchant Center or Shopify Google channel export into the workspace as feed.tsv (or pass --feed).")
    feed_rows = io.read_csv(feed)
    if not feed_rows or "id" not in feed_rows[0] or "title" not in feed_rows[0]:
        raise io.MissingInput(f"{feed.name} does not look like a Merchant Center feed (needs id and title columns).")
    prod_path = ws / "exports" / "products.csv"
    products = io.read_csv(prod_path) if prod_path.exists() else None
    reviews = None if args.reviews_integrated is None else (args.reviews_integrated == "yes")
    brand_hint = (data.get("brand_tokens") or [""])[0]
    result = compute(feed_rows, products, reviews, args.min_description, args.top, brand_hint)
    out = io.run_dir(ws, args.run_date)
    (out / "feedscore.md").write_text(render_md(result))
    (out / "feedscore.json").write_text(json.dumps(result, indent=2))
    print(f"feedscore: {result['scored']} products, {len(result['rebuild'])} under 7 -> {out / 'feedscore.md'}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("feedscore", help="10-point feed completeness score per product")
    p.add_argument("--feed", help="feed file, default <workspace>/feed.tsv or feed.csv")
    p.add_argument("--reviews-integrated", choices=["yes", "no"], help="whether product reviews are connected in Merchant Center")
    p.add_argument("--min-description", type=int, default=500)
    p.add_argument("--top", type=int, default=10, help="rank this many products by revenue from products.csv first")
    add_common(p)
    p.set_defaults(func=cmd_feedscore)
