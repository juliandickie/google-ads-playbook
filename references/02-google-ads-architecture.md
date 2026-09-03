# Google Ads Architecture - Standard

## Decisions Locked For This Project

These were open questions between sources. They are settled here so every prompt runs against one position. Change them here, not in a prompt.

1. PMax count. Run TWO PMax campaigns: one brand-allowed capture campaign and one brand-excluded scaling campaign, per the PMax Rules below.
2. Funnel phase sequencing. Phase 1 is branded search plus bestseller shopping only. Non-branded search enters in Phase 2 after Phase 1 has produced 10-20 conversions, alongside non-branded shopping and feed-only PMax. Problem-aware top-of-funnel search and Demand Gen wait for Phase 3, once Phases 1 and 2 are profitable. (The Webprofits playbook launches non-branded search on day one at 20-30 percent of budget; this Project does not.)
3. Feed descriptions fill toward 5,000 characters (see merchant-center-standards.md). The 160-500 character alternative is noted there, not used.
4. Scaling steps are 20-30 percent every 48-72 hours, gated by the 7, 14, and 30-day consistency rule.
5. Fixed numbers in this file are starting defaults from practitioner accounts, not sourced benchmarks. After 30 days of the account's own data, replace them with the account's history and say so.

## The 5 Pillars
Every account runs these five. Nothing else launches until they exist.

| Pillar | Job | Success metric |
|---|---|---|
| Branded search | Defend the name. Cheap conversions. | Impression share > 90% |
| Branded shopping | Own the product grid on brand queries | Impression share > 90% |
| Non-branded shopping | New customer acquisition, product-led | New customer ROAS |
| Non-branded search | New customer acquisition, intent-led | New customer ROAS |
| PMax remarketing | Warm audiences only, never prospecting | ROAS at a HIGH tROAS target |

## Measurement Standard (check this before anything else)
A broken measurement setup makes every other number in the account a guess.

- One primary conversion action. One. Multiple primaries compete and the algorithm splits its optimisation between them.
- Micro-conversions are secondary, always. Add-to-cart, newsletter signup, page view. Set one as primary and Google optimises towards cart abandoners.
- Click-to-call needs a duration minimum. 60 seconds. Without it you are paying to optimise towards wrong numbers and hang-ups.
- One backup source, cross-checked weekly. Platform, GA4, and the back end (Shopify, CRM) should agree within 15%.
- Attribution windows match across every action. Mismatched windows make campaign comparison meaningless.

BAD: 6 primary actions including Add To Cart, no GA4, 30-day window on one action and 7-day on another.
GOOD: 1 primary (Purchase), everything else secondary, GA4 and Shopify both connected, 30-day click window on all actions.

Flag it when: Shopify reports $100k and GA4 reports $50k. Something is broken. Without the backup source you would never know.

## PMax Rules
PMax defaults to stealing branded conversions and reporting a great ROAS while acquiring zero new customers.

- Brand exclusions: ON.
- Branded negative keyword list: applied.
- tROAS: set HIGHER than prospecting shopping. This is what forces it towards warm audiences instead of the cheapest conversions available.

BAD: PMax at 4.0 tROAS, no brand exclusions, reporting 11x. It is a remarketing campaign wearing a prospecting badge.
GOOD: PMax at 8.0 tROAS with brand excluded, reporting 6x on warm traffic only, and prospecting shopping reported separately.

The test: is this campaign a remarketing tool, or a branded traffic thief?

Run TWO PMax campaigns, not one: one that allows brand traffic (your capture campaign) and one with brand explicitly excluded (your scaling campaign). That gives you clean data on what Google is actually doing for you.

Feed-only PMax: a PMax campaign with only the product feed. No images, no videos, no headlines. This constrains the algorithm into running as a very smart shopping campaign, and at scale it often outperforms standard shopping.

Brand exclusions are about 85 percent effective on their own (Webprofits playbook). Treat the exclusion setting as the first layer, and always pair it with the branded negative keyword list and weekly search-term monitoring. Report the brand share of each PMax campaign's conversions monthly; the scaling campaign should sit under 15 percent.

The capture campaign exists to hold branded and warm traffic cheaply. The scaling campaign is the only one whose ROAS counts as new-customer performance. Never blend the two in reporting.

## Campaign Naming Convention
The model reads your campaign names to understand the account. Bad names give you mush no matter how good the prompt is.

[Type] | [Brand/NonBrand] | [Funnel] | [Product or Theme] | [Geo]

BAD: Campaign 1 - copy, Shopping NEW, test test
GOOD: Search | NonBrand | BOF | Magnesium | AU

## Bid Strategy Progression
Do not start on tROAS. You will kill the account before it has a chance to work. Strategy follows conversion volume in the trailing 30 days.

| Conversions (30 days) | Strategy | Notes |
|---|---|---|
| Under 15 | Maximize Clicks (or Manual CPC for full control) | Cold start. Set max CPC near target CPA x conversion rate x 1.5. Learning 3-5 days. eCPC no longer exists (removed March 2025). |
| 15-29 | Maximize Conversions, uncapped | Learning 7-14 days. Move on once CPA standard deviation is under 20 percent over 14 days. |
| 30+, no dynamic values | Target CPA | Google says 15 is enough; 30 is the reliable floor, 50 ideal. Set at 1.1-1.2x historical CPA. |
| 50+, with dynamic values | Target ROAS | Requires accurate conversion values. Set 20-30 percent BELOW the trailing 30-day ROAS (averaging 4x, start at 300 percent). |
| Brand protection | Target Impression Share, 95-100 percent | Search only. No conversion data needed. Manual CPC is the alternative. |

Adjusting a target: let it stabilise 14 days, then move 10-15 percent at a time, never more than 50 percent of its current value in one go, and never lower a tCPA by more than 15 percent at once.

Transition triggers (Google):

| From | To | Trigger |
|---|---|---|
| Manual CPC | Maximize Clicks | Ready to test automation |
| Maximize Clicks | Maximize Conversions | 15+ conversions in 30 days |
| Maximize Conversions | Target CPA | CPA standard deviation under 20 percent over 14 days and 30+ conversions |
| Target CPA | Target ROAS | 50+ conversions and dynamic values available |
| Any | Target Impression Share | Brand protection need identified |

Special cases: PMax always runs Maximize Conversions or Maximize Conversion Value (with or without a target). Demand Gen supports tCPC, tCPA, tROAS, and Max Clicks.

Portfolio bid strategies: use when several campaigns each have under 15 conversions but combine to 30 or more, or when you need a max CPC cap on tCPA or tROAS. Minimum three campaigns per portfolio, similar targets, and never mix brand and non-brand in one portfolio.

Attribution: data-driven attribution is the mandatory default (September 2025). Only DDA and last click remain. Every conversion action in the account uses the same model and window.

High-ticket exception: a $3,000 product might produce 3-5 conversions a month. Move to smart bidding at 3-5 purchase conversions per campaign, not 30-50, and use tROAS rather than tCPA. tCPA treats a $2,000 order the same as a $5,000 one.

Red flags: broad match on manual CPC (critical); a tCPA under 50 percent of actual CPA (critical, unrealistic target); smart bidding under 15 conversions a month (high); broad match with no negative lists (critical); several low-volume campaigns not grouped into a portfolio (medium).

## Scaling Cadence
Increase budget by no more than 20-30 percent every 48-72 hours. A big sudden jump puts smart bidding back into learning mode. Going from $5k/month to $20k/month means a staircase of 20-30 percent steps spaced 48-72 hours apart.

The multi-window gate. Scale only what shows the same green signal across the 7, 14, and 30-day windows at once. A campaign strong over 7 days and weak over 30 is noise. Scaling on noise is how accounts blow up. This rule outranks every other scaling instruction in this Project.

Saturation signals that say stop scaling: search impression share above 80 percent on the winning terms, rising CPC with flat conversion rate, marginal ROAS falling below break-even ROAS on the last two steps.

Before any budget or bid change, confirm no concurrent conversion, targeting, creative, or policy change would confound the read, define the evaluation window in conversion cycles, and record the before state so the change can be rolled back.

## Funnel Phase Sequencing

The order you build campaigns in matters more than almost anything else. The Launch Sequence table below is by spend tier; this section is by funnel phase. They agree.

Phase 1, bottom of funnel, start here.
- Branded search. Brand name only, exact match, manual CPC or target impression share, $10-20/day, 5-10 percent of budget. Should run at 5-10x ROAS minimum.
- Bestseller shopping. Top 3-10 products only, not the full catalogue. Do not exclude branded traffic yet; you want all the data you can get.
- Move on once these two have produced 10-20 conversions.

Phase 2, middle of funnel, where the scaling happens.
- Non-branded shopping. Identical to bestseller shopping with brand excluded under brand exclusions AND as a negative keyword.
- Feed-only PMax, brand excluded (the scaling campaign). No images, videos, or headlines; the feed only. Run it against non-branded shopping for 30 days and double down on the winner.
- Non-branded search on high-intent product terms, with the branded negative list applied.
- PMax capture campaign, brand allowed, at a HIGH tROAS, for warm and branded traffic.

Phase 3, top of funnel, only when Phase 2 is profitable.
- Demand Gen on YouTube and Shorts for cold audiences.
- Problem-aware search on terms where the product solves a specific problem.
- 90 percent of brands should not touch this phase until Phases 1 and 2 run profitably.

The 90-day plan.
- Weeks 1-2. Google Ads and Merchant Center set up, Shopify linked through the Google and YouTube channel, Tag Manager installed, purchase conversion tested with a real order before spending anything. Top 10 product titles optimised. Launch branded search at $5-10/day and bestseller shopping at $30-50/day.
- Weeks 3-4. Do not touch the campaigns. Check the search terms report twice a week and add negatives. At 10-20 conversions consider Max Conversions.
- Month 2. Launch non-branded shopping and feed-only PMax (brand excluded, $50-100/day, Max Conversions). Scale 20-25 percent every 48-72 hours on what works. At 30+ PMax conversions move to tROAS at 20-30 percent below actual.
- Month 3. Analyse the branded versus non-branded split. Expand winners to second-tier products. Test a second market. Evaluate Demand Gen if strong video creative exists.

## Budget Allocation
- Branded: 5-10% maximum. It is a defence line, not a growth line. Exact match brand terms only. Manual CPC or target impression share - never hand Google automated bid control on branded, it will inflate bids because it can. This campaign should run at 5-10x ROAS minimum.
- Non-branded prospecting: 60-70%.
- Remarketing (PMax + Display): 15-25%.
- Report new customer ROAS separately from blended ROAS. Always.

## Launch Sequence
| Phase | Spend / month | Launch |
|---|---|---|
| 1 | $0-10k | Branded search, branded shopping, non-branded shopping |
| 2 | $10-30k | Non-branded search, PMax remarketing with brand exclusions |
| 3 | $30-100k | Competitor search, Display remarketing, Demand Gen |
| 4 | $100k+ | TOF search tests, YouTube, geographic and category splits |

## Exclusion Rules
- Branded negative list on every non-branded campaign.
- Non-branded negative list on every branded campaign.
- Existing-customer audience excluded from all prospecting.
- Display placements: exclude apps and made-for-advertising sites.

## Flag Thresholds
| Signal | Flag when |
|---|---|
| Branded share of reported non-branded revenue | Above 20% |
| Search term conversion rate above 20% | Getting under 2% of campaign spend |
| Search term conversion rate below 3% | Getting over 5% of campaign spend |
| Campaign with no defined success metric | Always. Pause, do not optimise. |
| Two campaigns reaching the same audience | Always. One gets cut. |
| ROAS movement week on week | Down 20% or more |
| CPA movement week on week | Up 20% or more |

A search term needs 5 conversions minimum before you judge its rate.

Most accounts run 70-90% of their reported revenue off branded traffic. That is not Google doing its job, that is Meta doing the work and Google taking credit. Set up two custom reporting columns, branded revenue and non-branded revenue, and check them weekly.
