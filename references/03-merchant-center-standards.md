# Merchant Center Standards

## Why This File Matters Most Now
AI Max pulls attributes straight from the feed to rewrite product titles in real time. An empty feed gives it nothing to pull, so it writes generic titles and CTR tanks on the exact queries the product was meant to win.

## Title Formula
Brand + Product Type + Core Keyword + Key Feature + Use Case Benefit

Under 150 characters. Use the full length, but front-load: Google weights the first 70 characters most for search matching, so the terms people actually type go first. Audit titles against the search terms report monthly and reorder.

Equivalent formulation for variant-heavy catalogues (apparel, consumables): Brand + Product Name + Key Features + Variant (colour, size, flavour). Same rule, first 70 characters carry the match.

BAD (31 chars, 21% of the space used):
Magnesium Complex - 120 Count

GOOD (138 chars):
NordVital Magnesium Bisglycinate 400mg Sleep Supplement - Chelated High Absorption, 120 Vegan Capsules, Non-Drowsy Night Time Relaxation

By category:
| Category | Order |
|---|---|
| Supplements | Brand + Form + Ingredient + Dose + Outcome |
| Apparel | Brand + Gender + Product + Material + Colour + Size |
| Home goods | Brand + Product + Material + Dimension + Room |
| Electronics | Brand + Model + Product Type + Key Spec + Compatibility |

## Description Rules
- Fill to 5,000 characters. Do not stop at 500. (Project decision. The Webprofits playbook recommends 160-500 characters focused on technical specs and use cases; if a client insists on short descriptions, the first 500 characters must still carry specs, use cases, and long-tail terms, and must not repeat the title.)
- Cover: features, benefits, use cases, materials or ingredients, sizing and specs, common objections, reasons to choose this over alternatives.
- Include buyer keywords naturally.

HARD RULE: never name something the product is not.

BAD: "Unlike cheap aluminium alternatives, ours is solid steel." Google now serves you to aluminium searchers. They bounce. You pay for every one.
GOOD: "Solid steel construction, tested to 200kg."

## Required Back-End Attributes
GTIN, MPN, Brand, Google product category (deepest level available, as the numerical ID), Product type (your own taxonomy, it drives campaign segmentation), Condition, Availability, Shipping weight and dimensions, Colour, Size, Material, Age group, Gender, item_group_id (groups variants under one listing so ten sizes do not flood the results and split clicks).

Enhanced attributes, layer in once the core set is complete: additional_image_link and lifestyle_image_link (PMax pulls these for Display, YouTube, and Demand Gen), product_highlight and product_detail (bulleted specs in the Shopping tab, strong for electronics and technical products), short_title (Brand + core product name, for mobile and small banners where long titles truncate).

Missing GTIN suppresses eligibility for several Shopping surfaces.

BAD: Google product category "Health & Beauty"
GOOD: "Health & Beauty > Health Care > Vitamins & Supplements"

## Images
- Primary: studio, white background, product fills 75-90% of frame.
- Additional: lifestyle, scale reference, packaging, in-use.
- Test studio versus lifestyle as primary. 14 days minimum before you call it.

## Sale Pricing And Reviews
- Use sale_price and sale_price_effective_date. Never edit price down - the strikethrough badge only shows on a genuine sale price.
- Connect a product review feed before campaigns launch, not after. Star ratings lift Shopping CTR. Most review apps integrate with Merchant Center directly; otherwise upload the review feed.
- Connect seller ratings via Google Customer Reviews.

## Landing Page And Speed

Page speed is the largest single input to ad rank and quality score on Shopping traffic. Run speed tests on every product page before launch. Every product page carries clear CTAs, reviews, and AOV levers (bundles, quantity breaks, free-shipping thresholds, goes-well-with sections).

## Feed Completeness Score (out of 10)
One point each: title structure, description length, image type, Google product category specificity, product type, GTIN present, sale pricing configured, reviews integrated, shipping accurate, custom labels set.

Score every product in the top 10 by revenue. Rebuild anything under 7.

## Custom Labels
| Label | Use |
|---|---|
| custom_label_0 | Margin band: high / mid / low |
| custom_label_1 | Best seller: yes / no |
| custom_label_2 | Season |
| custom_label_3 | Price band |
| custom_label_4 | Stock level |

Bidding splits by custom label. An unlabelled feed cannot be bid on properly.

BAD: one Shopping campaign, all products, one bid.
GOOD: high-margin best sellers bid separately from low-margin clearance.
