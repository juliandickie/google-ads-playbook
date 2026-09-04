---
name: gads-precheck
description: Decide whether a brand should be on Google Ads yet and size the opportunity before spending. Use for "should we run Google Ads", readiness, the 22 signs, the revenue ceiling, or "how big is the Google opportunity".
---

# gads-precheck

Load the `gads` skill first. This skill does not need a full workspace; it needs a Keyword Planner export and the brand kit basics.

## Step 1 - the 22 signs

Open `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md`, section "Pre-check", and the 22 readiness signs in the captured library (`~/code/google-ads-audit-prompt-library/100M-GADs-Audit-Prompt-Library.md`, section "The 22 Signs"). Score the brand against each sign as yes or no with one line of evidence per sign, from the brand kit or the operator's answers. Five or more yes means the channel is worth building. Say the count and the strongest three signs.

## Step 2 - Meta as validation

If the brand runs Meta, ask for four things and record them in `<ws>/brand-kit.md` under Competitors and Offers: the highest-CTR creative angles (they become search headlines), top products by revenue (they become the first Shopping campaign), the language in the best comments (it becomes ad copy), and blended CAC (it becomes the Google target). No Meta account: say so and move on.

## Step 3 - the revenue ceiling

The operator exports Keyword Planner ideas for the brand name, the category terms, the three problems the product solves, and the top competitor's name, geo set to the market they ship to. Then:

```
${CLAUDE_PLUGIN_ROOT}/bin/gads ceiling <planner.csv> --aov <AOV> --margin <fraction> --brand "<brand tokens>" --currency <code> [--workspace <ws>]
```

Read `ceiling.md`. Present the brand and non-brand blocks separately, then the combined line, and repeat the sentence "this is a ceiling, not a forecast". Every rate used is a practitioner default; say that once.

## Step 4 - the leak

Explain, in two sentences, why the leak grows with Meta spend: paid awareness creates branded searches that a competitor bidding on the brand name collects. Point at the branded block of the ceiling as the number at stake.

Report: sign count, the ceiling table, the branded number at risk, and a one-line go or no-go with the reason.
