---
name: gads-audit
description: Run the six account audits on a Google Ads account - conversion tracking, branded leakage and true new-customer ROAS, PMax constraint, spend misallocation, Merchant Center, campaign roles. Use for "audit the account", "why does ROAS look good but revenue is flat", PMax stealing brand, wasted spend, or any Part 1 prompt.
---

# gads-audit

Load the `gads` skill first and run `gads validate`. Needs `campaigns.csv` and `search_terms.csv` at minimum; `keywords.csv`, `products.csv`, `conversion_actions.csv`, and `feed.tsv` make the audits complete. Run the pull with `--deep` (or `gads pull --deep-only` on existing exports) so `raw/deep-<date>/` holds the settings the exports cannot carry; read its `manifest.json` first and name any query that failed as missing evidence.

## Run the calculators, then let the CLI write the report

```
${CLAUDE_PLUGIN_ROOT}/bin/gads leakage --workspace <ws> --run-date <date>
${CLAUDE_PLUGIN_ROOT}/bin/gads misallocate --workspace <ws> --run-date <date>
${CLAUDE_PLUGIN_ROOT}/bin/gads windows --workspace <ws> --run-date <date>
${CLAUDE_PLUGIN_ROOT}/bin/gads audit --workspace <ws> --run-date <date> --executive
```

`gads audit` reads everything the workspace holds for that run date (the exports, the three calculator files, the deep pass, the brand SERP check and the reconciliation from this run or the latest earlier one) and writes `runs/<date>/audit.md`, `audit.json` and `audit-executive.md`. Its "Missing evidence" section is the list of what to produce next (a SERP check, a reconciliation, a deep pass); every control a missing source would have decided reads "no evidence".

Then review, do not rewrite: every recommendation in audit.md is a rule-drafted draft. Read each against the evidence it cites, correct the Change, Risk and Impact lines where the account's context says otherwise, add the recommendations only judgement can make (competitor names, audience mismatches, offer and landing page calls, anything the brand kit informs), delete a draft the evidence does not carry, and keep the numbering continuous. The executive version repeats the top three changes; re-read it after editing the technical one. Say in the report's Caveats which drafts were changed.

## The calculators behind it

Read the three markdown files in `runs/<date>/`. They are the evidence for audits 1.2, 1.4, and the scaling parts of 1.6. Do not restate their numbers from memory; quote the file. leakage.md and misallocation.md name the campaign window and the search-terms window they mix; the pull defaults keep them equal, so if the windows line says they differ, someone passed different flags, and you read that line before quoting the branded share.

## Then the six audits, in order

Prompts are in `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md` Part 1. For each, the reference that governs it and the evidence to cite:

1. Conversion tracking (1.1). Reference `06-google-audit-checklist.md` rows G42 to G49 and G-CT1 to G-CT3, method `07-conversion-tracking-execution.md`. Evidence: `exports/conversion_actions.csv` for configuration, and from the deep pass `conversion_action_metrics_90d.json` (which actions actually fired in 90 days, all_conversions and value per action), `campaign_conversion_split_90d.json` (per campaign, per action, conversions beside all_conversions: an action counted in all_conversions but not in conversions is secondary), `customer_conversion_goals.json` and `campaign_conversion_goals.json` (the biddable categories), `customer.json` (auto-tagging, enhanced conversions). The list of actions that fired is the finding that matters most; configuration alone hides it. Apply the measurement standard in `02`: one primary action, micro as secondary, matched windows, 60-second call minimum, back-end within 15 percent. The back-end check needs two more sources than the exports carry: the attribution tool that uploads conversions (SegMetrics, Hyros, Triple Whale, or GA4) and the cart or CRM that holds the orders (Spiffy, Shopify, ThriveCart, HubSpot). Compare three things for one window, purchase counts, lead counts, and purchase value, and write the table to `runs/<date>/reconciliation.md`. When the Google Ads account currency differs from the cart's, check both directions before trusting any ROAS: that uploaded conversion values are converted into the account currency, and that the attribution tool converts imported ad spend (a tool that shows the account-currency spend figure to the cent as its own currency is not converting). The upload direction can be settled from data without a settings screen: take three or four cart orders from a quiet fortnight, query the account's conversion values by click date and action (segments.date, segments.conversion_action_name, metrics.all_conversions_value on the campaign resource), and divide; a steady ratio near the day's exchange rate means the values arrive converted, a ratio near 1.0 means they arrive raw. Say which currency every ROAS is in. When a GA4 import into Google Ads records zero while the property does record the key event, check attribution before the link: run purchases by session source and by first-user source; if a hosted checkout on another domain carries the purchases and every one is Direct on both dimensions, cross-domain measurement to that domain is missing (GA4 Admin, data stream, configure your domains plus unwanted referrals) and the import has nothing tied to a click. A property with zero events in the window is dead; retire the Ads actions imported from it.
2. Branded leakage (1.2). Evidence: `runs/<date>/leakage.md`. Present the before and after table verbatim.
3. PMax constraint (1.3). Reference `02` PMax Rules and `06` G06, G07, G-PM1 to G-PM6. Evidence: campaigns.csv rows where channel type is PERFORMANCE_MAX, plus the PMax lines in leakage.md and its assumptions. Check the two-campaign structure exists; if it does not, the recommendation is to create it, not to tune the single campaign.
4. Spend misallocation (1.4). Evidence: `runs/<date>/misallocation.md`.
5. Merchant Center (1.5). Hand over to the gads-feed skill; include its `feedscore.md` in this report.
6. Campaign roles (1.6). Reference `06` G01 to G12. Evidence: campaigns.csv, `windows.md` for the decision metric, and from the deep pass `campaign_settings.json` (bidding strategy and targets, networks, geo type, budget, primary status and its reasons), `campaign_criteria.json` (locations, languages, schedules, device modifiers), `shared_sets.json` and `shared_criteria.json` and `adgroup_negatives.json` (which negative lists reach which campaign), `ads.json` and `ad_policy_topics.json` (strength, approval, policy topics), `campaign_assets.json`, `adgroup_assets.json`, `customer_assets.json`, `campaign_audiences.json`, `adgroup_audiences.json`, `user_lists.json`, `keyword_quality_30d.json`, `landing_pages_90d.json`, `device_90d.json`, `geo_90d.json`, and `change_events_28d.json` (who changed what in the last four weeks; an empty file is the G13 fail). For every campaign: job, signal, audience, decision metric, overlap. Then run the brand SERP check from the `gads` skill and cite `runs/<date>/brand-serp.md`: a brand campaign is recommended only for phrases and countries with a protect verdict, and an existing brand campaign on a no-bid phrase is a candidate to pause, with the free organic click as the reason.

## The deeper pass

When pro-marketing-ads is installed, run `/ads audit` on the same exports for the scored 80-check report and reconcile: anything it flags that the six audits did not gets its own line. When it is not installed, walk `06-google-audit-checklist.md` by section and mark each control pass, fail, or no evidence.

## Report shape

One section per audit, each ending in recommendations in the contract's format (campaign, issue, evidence with file and rows, rule, confidence, change, owner, approval state, risk, impact, rollback, measurement window). The reader is a person scanning for one fact, so the layout is a document, not a data dump:

- A heading per section and a `### Recommendation N - short name` heading per recommendation.
- One labelled fact per line, `**Label:** value`, with a blank line between lines. Findings, flags, per-campaign roles and the checklist walk use the same shape (`**G47:** fail (...)`, one control per line under a `### section` heading).
- No bullet lists and no pipe tables in the report body. Lettered sub-points become their own labelled lines (`**Change (a):** ...`).
- Every file cited is a clickable link, not a bare path: workspace files as absolute `file://` links (the operator reads the report outside the repo), playbook references as GitHub blob URLs. A link must resolve on disk; check every target before shipping.
- A `## Data used` block at the top links every source, and a `**Follow-up:**` line points at the latest readout when one exists.
- Dates as YYYY-MM-DD. Then the five mistakes as a yes or no table, one row each: no branded campaign (answer from `brand-serp.md`: it is a yes only where a protect verdict has no campaign behind it; first organically with no competitor ads is "not needed today", not a mistake); traffic sent to the homepage instead of a matched landing page; PMax left to run wild with brand allowed everywhere; scaling before there is data; the product feed ignored. The full text is the section "The 5 Mistakes These Prompts Keep Finding" in the captured library (`~/code/google-ads-audit-prompt-library/100M-GADs-Audit-Prompt-Library.md`) when it is on this machine. Close with the three changes that move new-customer ROAS most, in order.
