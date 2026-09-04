---
name: gads-feed
description: Merchant Center feed audit and rebuild - completeness score, title formula, descriptions, attributes, custom labels. Use for "fix the feed", product titles, Shopping performance, GTIN, custom labels, or prompts 1.5 and 2.6.
---

# gads-feed

Load the `gads` skill first. Needs `<ws>/feed.tsv` (Merchant Center or Shopify Google channel export, as supplied) and ideally `exports/products.csv` for revenue ranking. Reference `03-merchant-center-standards.md`.

## Score

```
${CLAUDE_PLUGIN_ROOT}/bin/gads feedscore --workspace <ws> --reviews-integrated <yes|no>
```

Ask the operator whether product reviews are connected in Merchant Center before running; the script cannot see it. Read `runs/<date>/feedscore.md`. Products under 7 are the rebuild list.

## Audit (prompt 1.5)

For the top 10 by revenue, walk the ten points with the score as evidence and the standards in `03` as the bar. Say which points fail and why in one line each. The AI Max point from `03`: an empty attribute is a title Google will rewrite badly.

## Rebuild (prompt 2.6)

For each rebuild candidate, run the title prompt (formula Brand + Product Type + Core Keyword + Key Feature + Use Case Benefit, under 150 characters, the most searched terms in the first 70) and the description prompt (fill toward 5,000 characters, cover features, benefits, use cases, materials, specs, objections, reasons to choose; never name what the product is not). Check every claim against the product page. Propose custom labels by margin band and best-seller status.

Output `<ws>/build/feed-rebuild.md` with a table: item id, current title, proposed title, description length before and after, attributes to add, labels. The operator applies it in Merchant Center or the Shopify channel; this plugin does not write feeds.

Report: score distribution, the rebuild list, and the three attributes most often missing across the catalogue.
