---
name: gads-build
description: Build the account from research to launch-ready structure - customer language, competitor angle map, keyword universe, campaign architecture, RSA copy, landing page briefs. Use for "build the campaigns", keyword research, RSA headlines, competitor angles, landing page brief, or any Part 2 prompt.
---

# gads-build

Load the `gads` skill first. Needs `brand-kit.md` and `brand-brain.md`; the audits' `runs/<date>/` files if they exist. References: `02-google-ads-architecture.md` for structure and the locked decisions, `04-ad-copy-frameworks.md` for copy.

Prompts are in `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md` Part 2. Run them in order; each feeds the next.

## 2.1 Customer language

If the Copy School plugin is installed, use its voc-research skill (Mode B, review and forum mining) and ask it for the 25-row table with the Possible Ad Angle column added. Otherwise run prompt 2.1 as written; it carries the same rules (verbatim only, three-source triangulation, low yield is normal). Save as `<ws>/research/customer-language.md`.

## 2.2 Competitor angle map

Prompt 2.2 with Ads Transparency Center and Meta Ad Library as sources, then the validated versus white-space follow-up. Three competitors on one hook is validated; nobody on an angle the research surfaced is white space. Save as `<ws>/research/competitor-angles.md`.

## 2.3 Keyword universe

Prompt 2.3, then the 30-day prioritisation. Cross-check the universe against `exports/search_terms.csv`: any converting term the universe missed goes in. Every keyword carries funnel stage, intent, match type, campaign and ad group, landing page angle. Save as `<ws>/build/keywords.md`.

## 2.4 Campaign architecture

Prompt 2.4, constrained by the locked decisions: the nine campaign types, two PMax campaigns, non-branded search in Phase 2, naming `[Type] | [Brand/NonBrand] | [Funnel] | [Product or Theme] | [Geo]`, bidding from the progression table in `02`, budget split 5-10 / 60-70 / 15-25. Then the role explanation follow-up. Save as `<ws>/build/architecture.md`.

## 2.5 RSA copy

Prompt 2.5 per keyword cluster, then the three variations. Output must satisfy the RSA Output Spec in `04` (15 and 4, counts printed, H1 matches the query, sidecars, output order, self-check). Negatives come from the search terms report or the universe, never a generic list. Save as `<ws>/build/rsa/<cluster>.md`.

## 2.6 Merchant Center rebuild

Hand over to the gads-feed skill.

## 2.7 Landing page briefs

If Copy School is installed, use its 10x-landing-pages skill (Mode B, Write) with the awareness stage from the keyword universe and the customer language file as research, and ask for the five angle variations at the end. Otherwise run prompt 2.7 as written (Rule of One first, hero mirrors the query, proof for every claim, drivers and barriers, the 5-second test). Save as `<ws>/build/landing/<keyword>.md`.

Report: the files written, the launch order from the architecture, and what the operator must supply before launch (tracking test with a real order, feed titles, budgets approved).
