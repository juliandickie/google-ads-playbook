---
name: gads-manage
description: Ongoing management - the daily audit, the weekly scaling plan behind the 7/14/30-day gate, and the ROAS-drop diagnostic in the fixed order. Use for "daily check", "what should I scale", "ROAS dropped", weekly review, or any Part 4 prompt.
---

# gads-manage

Load the `gads` skill first. Refresh the data, then run the gate:

```
${CLAUDE_PLUGIN_ROOT}/bin/gads pull --customer <id> --login-customer <mcc> --days 70 --search-terms-days 70 --workspace <ws>
${CLAUDE_PLUGIN_ROOT}/bin/gads windows --workspace <ws>
${CLAUDE_PLUGIN_ROOT}/bin/gads leakage --workspace <ws>
```

(70 days for both so the 30-versus-prior-30 window survives a quiet first day and the leakage read uses one window. Use `normalise` on fresh UI exports when the API is unavailable.)

Once a month, or when a competitor is suspected of bidding on the brand, rerun the brand SERP check from the `gads` skill and compare with the previous `brand-serp.md`: a phrase that moved from no bid to protect (a competitor ad appeared, or the organic rank slipped) is the one change this skill may recommend outside the scaling gate, as a draft brand campaign for that phrase and country.

## 4.1 Daily audit

Prompt 4.1 from `references/10-prompts.md` Part 4 with `windows.md` as the 7-day evidence and `leakage.md` for branded leakage. Flags from `02`: ROAS down 20 percent or more, CPA up 20 percent or more, budget-limited winners (the budget-limited line in windows.md), rank-limited campaigns, wasted-spend queries, products spending with zero conversions (products.csv). Then the action-list follow-up in the contract's recommendation format.

## 4.2 Weekly scaling plan

`windows.md` is the plan. Scale only campaigns marked scale, by the step it names (20 percent, re-read at 72 hours). Hold and cut as marked, with the reasons quoted. Never override a hold because the 7-day number looks good; that is the rule this skill exists to enforce. Then the testing roadmap follow-up: 3 keyword, 3 creative, 2 landing page, 2 feed, 1 structure test, ranked by impact and difficulty.

## 4.3 ROAS drop

Prompt 4.3, but work the diagnostic order from `references/09-project-instructions.md` and never skip to creative: tracking (conversion_actions.csv, and whether the measurement changed), budget or bid constraint (the Budget limited and Rank lost impression share lines under each campaign in windows.md), search-terms drift (fresh search_terms.csv versus the last run's misallocation.md), auction pressure, feed or landing page change, seasonality, creative fatigue last. Rank causes by probability given the data and hand back a test order.

Report: the verdict table from windows.md, the action list, and the one number the operator should watch until the next run.
