# Prompt Library In Run Order

Every prompt from the $100M GADs library, in the order the 60-minute run uses them. Prompts 2.1 and 2.7 are replaced with stronger versions (Copy School voice-of-customer and landing-page methods folded in). Paste one at a time. Fill the square-bracket fields from the brand kit.

## The 60-Minute Run Order

- Minutes 0-15. Upload everything (see SETUP.md). Run the initialisation prompt. Save the brand brain output as a file and re-upload it.
- Minutes 15-30. Run all six audit prompts in sequence.
- Minutes 30-45. Run customer language mining, the competitor angle map, and the keyword universe.
- Minutes 45-55. Run campaign architecture and RSA copy production.
- Minutes 55-60. Run the Merchant Center rebuild on the top 10 products.
- Following days. Landing page briefs, creative concepts, then the daily audit from that point forward.

## Pre-check (before spending anything)

Score the brand against the 22 readiness signs in the library, pull the four Meta validation signals (top-CTR angles, top-revenue products, best comment language, blended CAC), then run the revenue-ceiling model. Use Keyword Planner volume, not Trends.

### The 5-Minute Revenue Audit

```
CONTEXT
I'm building a Google Ads opportunity model for [BRAND / DOMAIN]: a [MARKET] [CATEGORY] brand. AOV: [CURRENCY][AOV]. Market: [MARKET].

TASK
Estimate monthly Google search volume for the keyword groups below, then run the calculation in Step 3.

STEP 1 - VOLUME ESTIMATES
For each group, list the actual keywords people type into Google (not conversational questions), with an estimated monthly search volume for each. Include broad, phrase, long-tail and common misspelling variations. State your source or confidence level for every number, and flag any figure you cannot ground in real data.

GROUP A - Brand terms
- [BRAND NAME] (exclude generic uses of the word "[AMBIGUOUS WORD IN BRAND NAME, IF ANY]". Brand intent only)

GROUP B - Competitor brand terms
- [COMPETITOR 1]
- [COMPETITOR 2]
- [COMPETITOR 3]

GROUP C - Category terms
- [CATEGORY TERM 1]
- [CATEGORY TERM 2]
- [CATEGORY TERM 3]

GROUP D - Problem / intent terms
- [PROBLEM 1 THE PRODUCT SOLVES]
- [PROBLEM 2 THE PRODUCT SOLVES]
- [PROBLEM 3 THE PRODUCT SOLVES]

STEP 2 - SUBTOTALS
- Brand volume = Group A + Group B
- Non-brand volume = Group C + Group D

STEP 3 - THE CALCULATION
Run these separately, because brand and non-brand behave very differently.

BRAND
Clicks    = brand volume x 20%
Purchases = clicks x 10%
Revenue   = purchases x [CURRENCY][AOV]
Media cost = clicks x [BRAND CPC]
Profit    = revenue x [GROSS MARGIN %] - media cost

NON-BRAND
Clicks    = non-brand volume x 4%
Purchases = clicks x 2%
Revenue   = purchases x [CURRENCY][AOV]
Media cost = clicks x [NON-BRAND CPC]
Profit    = revenue x [GROSS MARGIN %] - media cost

TOTAL
- Combined monthly revenue potential
- Combined monthly media cost
- Combined monthly gross profit
- Blended ROAS

OUTPUT FORMAT
1. A table per group: keyword | est. monthly volume | confidence | notes
2. A summary table of the Step 3 calculation
3. One paragraph: the single biggest opportunity in this account
```

## Part 0 - Initialisation

### The Initialisation Prompt

```
Act as the Google Ads strategy brain for this brand. Read all uploaded context and build a working brand profile covering: ICP, core pain points, buying triggers, objections, the emotional language customers use, top products by revenue and margin, strongest offers, competitor positioning, current funnel gaps, and the biggest Google Ads opportunities you see. Do not make recommendations yet. Summarise the context first, then tell me what critical information is missing before you could build a strategy.
```

Save the output as a file and re-upload it to the Project. This becomes the brand brain. Every subsequent prompt references it.

## Part 1 - The Six Account Audits

Each audit runs against the 80-control checklist in 06-google-audit-checklist.md. Audit 1.1 uses the execution method in 07-conversion-tracking-execution.md.

### 1.1 The Conversion Tracking Audit

```
Audit my conversion tracking setup. Review every conversion action, its primary/secondary designation, attribution model, conversion window, and counting method. Flag: multiple primary actions competing with each other, add-to-cart or micro-conversions set as primary, missing backup tracking sources, click-to-call set as primary without a duration minimum, mismatched attribution windows between actions, and any action producing suspiciously round or inflated numbers. For each issue, explain what it breaks downstream in the algorithm's optimisation.
```

### 1.2 The Branded Leakage Audit

```
Analyse my search terms report and campaign structure. Identify every instance where branded traffic is appearing in non-branded campaigns, and every instance where non-branded traffic is appearing in branded campaigns. Calculate what percentage of my reported non-branded revenue is actually branded traffic. Then recalculate my true new customer acquisition ROAS with branded traffic stripped out. Show me the before and after.
```

### 1.3 The PMax Constraint Audit

```
Review every PMax campaign. Check for: brand exclusions setting enabled, branded negative keyword lists applied, tROAS target level relative to my prospecting shopping campaigns, asset group structure, and audience signal configuration. Tell me whether each PMax campaign is functioning as a remarketing tool or as a branded traffic thief. For each campaign, recommend the specific tROAS target and exclusion setup that would force it into remarketing.
```

### 1.4 The Spend Misallocation Audit

```
Analyse my search terms report across the last 6 months. Filter for terms with more than 5 conversions. Sort by conversion rate descending. Identify every term with a conversion rate above 20% receiving less than 2% of total campaign spend. Then identify every term with a conversion rate below 3% receiving more than 5% of total spend. Build a reallocation plan showing exactly which terms should be pulled into dedicated campaigns with their own budgets.
```

### 1.5 The Merchant Center Audit

```
Audit my product feed for missed Google Shopping opportunities. For each of my top 10 products by revenue, review: title structure and character usage, description length and keyword coverage, image type (lifestyle versus studio), Google product category specificity, product type, GTIN presence, sale pricing configuration, review integration, shipping accuracy, and custom label setup. Score each product out of 10 on feed completeness. Then rewrite the titles for my bottom 5 scoring products using the structure: Brand + Product Type + Core Keyword + Key Feature + Use Case Benefit, staying under 150 characters.
```

### 1.6 The Campaign Role Audit

```
List every campaign in my account. For each one, tell me: what job it performs in the funnel, what signal it produces for the algorithm, what audience it reaches, what metric decides whether it scales or gets cut, and whether it overlaps with any other campaign. Flag every campaign with no clear role, redundant coverage, or no defined success metric.
```

## Part 2 - The Seven Build Prompts

### 2.1 Customer Language Mining

Replaces the library's original 2.1 with the Copy School voice-of-customer method folded in. Same output table, stricter evidence.

```
Mine customer language for [PRODUCT CATEGORY]. Sources, in priority order: our own sales call notes and support tickets (uploaded), 4-star Amazon reviews of our product and the three closest competitors, review sites for the category, Reddit and niche forums ("[topic] forum"), YouTube comments on category videos, TikTok comments on category videos, Product Hunt comments on anything hired to do the same job. On Amazon, search inside reviews for "tired of", "tried", and "wasn't until" to surface problems, failed solutions, and switch moments.

Rules. Capture verbatim; never paraphrase, a paraphrase is your invention wearing evidence's clothes. Keep only lines that could not have been written at a marketer's desk; if it reads like ad copy, drop it. Expect a low yield, roughly 3-4 sticky lines per 100 responses is normal. Treat one source as a hypothesis; a theme counts only when it appears in three independent sources. Flag any line from a competitor's customers rather than ours.

Output a table with at least 25 rows: Quote (verbatim) / Source and URL / Pain Point / What They Already Tried and Why It Failed / Desired Outcome / Funnel Stage (unaware, problem-aware, solution-aware, product-aware) / Possible Ad Angle. Then list the three themes with the strongest triangulation, the single line with the highest emotional tension, and the gaps where we have no evidence yet.
```

### 2.2 Competitor Angle Map

```
Research these competitors: [COMPETITOR 1], [COMPETITOR 2], [COMPETITOR 3]. Use Google Ads Transparency Center, Meta Ad Library, their landing pages, product pages, offers, guarantees, reviews, and email capture flows. Build a table showing: offer, main promise, ad hooks, landing page angle, proof used, objections handled, pricing position, and what they are NOT saying.
```

Then:

```
Based on this competitor research, identify the 5 most validated market angles and the 5 biggest white-space angles we could own. For each angle, explain which funnel stage it belongs to and which campaign type should test it first.
```

### 2.3 Full Keyword Universe

```
Using the customer language research, competitor analysis, and my product pages, build a complete Google Ads keyword universe for [BRAND]. Split into: branded, competitor, high-intent product, problem-aware, solution-aware, comparison, ingredient/material, use-case, gift/occasion, and negative keywords. For each keyword include: funnel stage, intent level, recommended match type, campaign and ad group assignment, and the landing page angle it should point to.
```

Then:

```
Now prioritise this into a 30-day launch plan. Separate must-launch keywords from phase 2 tests. Flag any keyword that is high volume but low commercial intent, and explain why it would waste budget.
```

### 2.4 Campaign Architecture

```
Turn the finalised keyword research into a complete Google Ads account structure. Include campaign names, ad group names, keyword match types, bidding strategy per campaign, starting budget split, exclusions, negative keyword rules, and the launch sequence. Use this structure: branded search, branded shopping, non-branded shopping, non-branded search, competitor search, PMax remarketing with brand exclusions, display remarketing, Demand Gen, and TOF search tests.
```

Then:

```
Explain why each campaign exists, what signal it produces, what audience it reaches, and what metric decides whether it scales, holds, or gets cut.
```

### 2.5 RSA Copy Production

```
Write responsive search ad copy for [PRODUCT] targeting [KEYWORD]. Funnel stage: [BOF/MOF/TOF]. Use the customer language and competitor gap analysis from earlier. Give me 15 headlines under 30 characters and 4 descriptions under 90 characters. Include benefit-led, problem-led, proof-led, offer-led, and urgency-led variations. Headline 1 must match the search intent directly.
```

Then:

```
Create 3 full ad variations for this keyword: one direct-response version, one proof-heavy version, and one problem-agitation version. Explain which audience segment each variation targets.
```

### 2.6 Merchant Center Rebuild

```
Rewrite this product title for Google Shopping using the structure: Brand + Product Type + Core Keyword + Key Feature + Use Case Benefit. Stay under 150 characters. Give me 10 variations ranked by likely search intent, and explain which search cluster each variation targets.
```

Then:

```
Write a Merchant Center description for [PRODUCT] using up to 5,000 characters. Cover features, benefits, use cases, materials or ingredients, sizing and specs, common objections, and reasons to choose this over alternatives. Include all relevant buyer keywords naturally. Never include keywords describing something this product is not.
```

### 2.7 Landing Page Briefs

Replaces the library's original 2.7 with the Copy School landing-page method folded in (awareness ladder, Rule of One, message match).

```
Build a landing page brief for [PRODUCT] targeting people searching [KEYWORD]. Awareness stage: [UNAWARE / PROBLEM-AWARE / SOLUTION-AWARE / PRODUCT-AWARE / MOST-AWARE]. The stage sets the hook: problem-aware pages open on the pain in the customer's words, solution-aware pages open on the mechanism and why it beats what they tried, product-aware pages open on the offer, proof, and guarantee.

Rule of One first: one reader (from the brand kit target buyer), one big idea, one promise, one offer. State all four before the structure. Then the structure: hero headline that reflects the search query directly (the first screen must continue the ad), subheadline, proof bar, problem section using verbatim customer language from the research, mechanism section, product section, comparison section, reviews, objection handling in the customers' own words, FAQ, CTA. Every claim on the page must be one we can substantiate; list the proof each claim needs. Mark the drivers (what pulls them toward buying) and barriers (what stops them) the page must address. Finish with a 5-second test question: what would a stranger say this page offers after 5 seconds on the hero?
```

Then:

```
Create 5 landing page angle variations for this product based on different search intents. For each: hero headline, core promise, proof required, objections to handle, and CTA.
```

## Part 3 - Creative And YouTube Production

Rank concepts by evidence tier before producing anything (05-creative-production-system.md, strategy layer). Pick the format from the selection framework and feed it into the Style bracket in 3.1.

### 3.1 The Ad Concept Prompt

```
Create a 9-shot YouTube ad concept for [PRODUCT] based on this angle: [ANGLE]. Style: [claymation / Pixar 3D / UGC / cinematic product demo]. For each shot include: scene description, voiceover line, and on-screen text. Follow this narrative arc: relatable problem, villain reveal, villain escalation, hero mechanism introduction, mechanism at work, product reveal, transformation, social proof, CTA with offer.
```

### 3.2 The Static Generation Prompt

```
For each of the 9 shots above, write a GPT Images 2.0 prompt. Include: style direction, lighting setup, camera angle, character description, environment, product placement, colour palette using [BRAND HEX CODES], and any on-screen text with exact spelling. Specify 2K resolution and 9:16 aspect ratio.
```

### 3.3 The Animation Prompt

```
For each generated frame, write a Seedance 2.5 animation prompt. Include: movement style, character action, camera direction (push in, pan, static), native audio cues, duration in seconds, and output specification at 1080p.
```

### 3.4 The Concept Multiplier

```
Create 5 new creative concepts drawn from the strongest customer pain points in the earlier research. Each concept needs: hook, visual metaphor, full script, image prompts, animation prompts, and CTA. Make each concept target a different pain point and a different funnel stage.
```

### 3.5 The Meta Repurposing Prompt

```
Review my top-performing Meta creatives. For each one, identify the hook, the core angle, the proof used, and the CTA structure. Then rewrite each as a YouTube-native ad concept optimised for [6-second bumper / 15-second in-stream / 30-second in-stream]. Explain what changes between the Meta version and the YouTube version and why.
```

## Part 4 - Ongoing Management

Run 4.1 daily, 4.2 weekly, 4.3 whenever ROAS moves more than 20 percent. Connect the Google Ads MCP or upload CSV exports.

### 4.1 Daily Audit

```
Pull the last 7 days of Google Ads performance and compare against the previous 7 days. For each campaign show: spend, revenue, ROAS, conversions, CPA, CPC, CTR, impression share, search lost IS rank, search lost IS budget, and top search terms. Flag: ROAS down 20% or more, CPA up 20% or more, budget-limited winners, rank-limited campaigns, branded leakage in non-branded campaigns, wasted spend queries, and products spending with zero conversions.
```

Then:

```
Turn this audit into an action list. For each action include: campaign, issue, supporting evidence, recommended change, risk level, and expected impact.
```

### 4.2 Weekly Scaling Plan

```
Compare performance across 7, 14, and 30-day windows. Identify campaigns, products, keywords, ads, and landing pages showing consistent green signals across ALL THREE windows. Recommend which budgets to increase by 15-20%, which to hold, which to decrease. Do not recommend scaling anything unless the signal is consistent across multiple windows.
```

Then:

```
Create next week's testing roadmap. Include 3 keyword tests, 3 creative tests, 2 landing page tests, 2 feed tests, and 1 campaign structure test. Rank by expected impact and implementation difficulty.
```

### 4.3 The Diagnostic Prompt

```
My [CAMPAIGN NAME] has dropped [X]% in ROAS over the last 14 days. Analyse every possible cause: auction pressure changes, search terms drift, landing page performance, feed changes, seasonality, competitor entry, bid strategy learning, budget constraint, conversion tracking issues, or creative fatigue. Rank the likely causes by probability given the data, and give me a diagnostic sequence to confirm which one it is.
```
