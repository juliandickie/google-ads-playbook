---
name: gads-audit
description: Run the six account audits on a Google Ads account - conversion tracking, branded leakage and true new-customer ROAS, PMax constraint, spend misallocation, Merchant Center, campaign roles. Use for "audit the account", "why does ROAS look good but revenue is flat", PMax stealing brand, wasted spend, or any Part 1 prompt.
---

# gads-audit

Load the `gads` skill first and run `gads validate`. Needs `campaigns.csv` and `search_terms.csv` at minimum; `keywords.csv`, `products.csv`, `conversion_actions.csv`, and `feed.tsv` make the audits complete.

## Run the calculators first

```
${CLAUDE_PLUGIN_ROOT}/bin/gads leakage --workspace <ws>
${CLAUDE_PLUGIN_ROOT}/bin/gads misallocate --workspace <ws>
${CLAUDE_PLUGIN_ROOT}/bin/gads windows --workspace <ws>
```

Read the three markdown files in `runs/<date>/`. They are the evidence for audits 1.2, 1.4, and the scaling parts of 1.6. Do not restate their numbers from memory; quote the file. leakage.md and misallocation.md name the campaign window and the search-terms window they mix; for a window-consistent leakage read, pull with --search-terms-days equal to --days first, or read the windows line before quoting the branded share.

## Then the six audits, in order

Prompts are in `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md` Part 1. For each, the reference that governs it and the evidence to cite:

1. Conversion tracking (1.1). Reference `06-google-audit-checklist.md` rows G42 to G49 and G-CT1 to G-CT3, method `07-conversion-tracking-execution.md`. Evidence: `exports/conversion_actions.csv`. Apply the measurement standard in `02`: one primary action, micro as secondary, matched windows, 60-second call minimum, back-end within 15 percent.
2. Branded leakage (1.2). Evidence: `runs/<date>/leakage.md`. Present the before and after table verbatim.
3. PMax constraint (1.3). Reference `02` PMax Rules and `06` G06, G07, G-PM1 to G-PM6. Evidence: campaigns.csv rows where channel type is PERFORMANCE_MAX, plus the PMax lines in leakage.md and its assumptions. Check the two-campaign structure exists; if it does not, the recommendation is to create it, not to tune the single campaign.
4. Spend misallocation (1.4). Evidence: `runs/<date>/misallocation.md`.
5. Merchant Center (1.5). Hand over to the gads-feed skill; include its `feedscore.md` in this report.
6. Campaign roles (1.6). Reference `06` G01 to G12. Evidence: campaigns.csv, `windows.md` for the decision metric. For every campaign: job, signal, audience, decision metric, overlap.

## The deeper pass

When pro-marketing-ads is installed, run `/ads audit` on the same exports for the scored 80-check report and reconcile: anything it flags that the six audits did not gets its own line. When it is not installed, walk `06-google-audit-checklist.md` by section and mark each control pass, fail, or no evidence.

## Report shape

One section per audit, each ending in recommendations in the contract's format (campaign, issue, evidence with file and rows, rule, confidence, change, owner, approval state, risk, impact, rollback, measurement window). Then the five mistakes checklist from `02` as a yes or no table. Close with the three changes that move new-customer ROAS most, in order.
