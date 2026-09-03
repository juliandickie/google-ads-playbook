# Ad Copy Frameworks

## RSA Requirements
- 15 headlines, each under 30 characters.
- 4 descriptions, each under 90 characters.
- Headline 1 matches the search query directly.
- Pin nothing unless there is a legal or compliance reason.
- All five angles covered across the 15.

## The Five Headline Angles
| Angle | What it does | Shape |
|---|---|---|
| Benefit-led | Names the outcome | "Sleep Through The Night" |
| Problem-led | Names the pain | "Tired Of 3am Wake-Ups?" |
| Proof-led | Names the evidence | "12,000+ 5-Star Reviews" |
| Offer-led | Names the deal | "Free Shipping Over $50" |
| Urgency-led | Names the deadline | "Ends Sunday Midnight" |

## Worked Example
Keyword: magnesium glycinate for sleep. Stage: BOF

Headlines:
1. Magnesium Glycinate Sleep
2. Sleep Through The Night
3. Wake Without Grogginess
4. 400mg Glycinate Per Dose
5. Bisglycinate, Not Oxide
6. Third-Party Tested
7. 12,000+ 5-Star Reviews
8. Doctor Formulated
9. Tired Of 3am Wake-Ups?
10. No Melatonin Hangover
11. Sleep Deeper In 7 Nights
12. Free Shipping Over $50
13. 60-Night Money Back
14. Subscribe & Save 20%
15. Ends Sunday Midnight

Descriptions:
1. Magnesium bisglycinate absorbs where oxide doesn't. 400mg a dose. Free shipping $50+.
2. Fall asleep faster without the melatonin hangover. 60-night guarantee.
3. 12,000+ five-star reviews. Third-party tested. Doctor formulated.
4. Tired of 3am wake-ups? Sleep deeper within 7 nights or get your money back.

Headline 1 repeats the query. Angles 1-5 all appear. Nothing is pinned.

## Copy By Funnel Stage
| Stage | Job | Lead with |
|---|---|---|
| BOF | Make the product the obvious answer | Exact query match, offer, guarantee |
| MOF | Make the benefit believable | Mechanism, proof, comparison |
| TOF | Make the problem impossible to ignore | The pain, in the customer's own words |

## Copy By Keyword Type
| Keyword type | Headline 1 | Description leads with |
|---|---|---|
| Branded | The brand name | Official store, guarantee, range |
| Transactional | The exact product phrase | Price, shipping, stock |
| Comparison | "X vs Y" or "Best X for Y" | The differentiator |
| Informational | The question asked | The answer, then the product |

## Required Extensions
Sitelinks (minimum 4), Callouts (minimum 4), Structured snippets, Price extension, Promotion extension when a live offer exists, Image extension, Lead form only where the model is lead generation.

## Rules
Every headline stands alone. RSA shuffles them, so no headline may depend on another.

BAD: H1 "Our Magnesium Is" / H2 "Better Absorbed"
GOOD: H1 "Magnesium Glycinate Sleep" / H2 "Bisglycinate, Not Oxide"

No claim in an ad that is not on the landing page. It fails the query-to-page match and it fails Google's review.

Customer language over brand language. Pull the words from reviews.

BAD: "Optimised bioavailability profile"
GOOD: "Absorbs where cheap magnesium doesn't"

## RSA Output Spec (enforcement layer)

Adapted from marketingskills rsa-output-spec.md (MIT, Corey Haines). When asked for RSAs, the output must comply. Do not ship an RSA that fails a check.

Hard limits per RSA.
- Exactly 15 headlines, each 30 characters or fewer, rendered as `1. text (NN chars)` so the count is visible.
- Exactly 4 descriptions, each 90 characters or fewer, counts printed.
- Up to 2 paths, each 15 characters or fewer. Final URL present, https.
- Pinning stated explicitly. Default unpinned. Pin only for a legal or compliance reason.
- Headline 1 matches the search query directly. All five angles appear across the 15.
- Google allows 3 RSAs per ad group. More than 3 requested means more than one ad group.

Required sidecars with every RSA request.
1. Ad group structure, labelled, with theme, keywords and match types, and which RSAs map to it.
2. Negative keywords, labelled, minimum 8, split campaign-level and ad-group-level, derived from the search terms report or the keyword universe, never a generic starter list.
3. Sitelinks (4 or more, title 25 characters, descriptions 35), callouts (4 or more, 25 characters), structured snippets where relevant.

Output order, so nothing important is lost if the response runs long: ad group structure, negative keywords, sitelinks, callouts, then RSA1, RSA2, RSA3.

Self-check before responding. Each RSA has exactly 15 and 4. Every headline is 30 or under, every description 90 or under, counts printed. Negatives labelled and 8 or more. Ad group structure labelled. Every claim exists on the landing page. If any check fails, rewrite before responding.

## Six Additional Frameworks (second angle source)

From claude-ads copy-frameworks.md (MIT, AgriciDaniel). The five angles above are organised by what the headline names. These six are organised by persuasion structure. Use them to generate the description lines and full-ad variations, then map each line back to one of the five angles.

| Framework | Steps | Best for | RSA headline shape | RSA description shape |
|---|---|---|---|---|
| AIDA | Attention, Interest, Desire, Action | Cold audiences, launches | [Attention hook] [Benefit] | [Interest detail]. [Desire benefit]. [Action CTA with urgency]. |
| PAS | Problem, Agitate, Solution | Pain-point products, retargeting | [Problem keyword] solved | [Problem]. [Agitated pain]. [Solution]. [CTA with benefit]. |
| BAB | Before, After, Bridge | Transformation offers | From [Before] to [After] | [Before pain]. [After benefit]. [Bridge product]. [CTA]. |
| 4P | Promise, Picture, Proof, Push | High-ticket, premium | [Promise] [Proof stat] | [Promise]. [Picture result]. [Proof]. [Push CTA]. |
| FAB | Features, Advantages, Benefits | Technical products, comparison shoppers | [Feature] [Key advantage] | [Feature]. [Advantage vs alternatives]. [Benefit]. [CTA]. |
| Star-Story-Solution | Star, Story, Solution | Brand storytelling, UGC | [Star] trusts [Brand] | [Star intro]. [Story arc]. [Solution with brand]. [CTA]. |

Selection by audience temperature.
- Cold: AIDA or Star-Story-Solution for awareness, BAB or PAS for consideration, AIDA with a hard CTA for conversion.
- Warm: PAS or 4P for consideration, FAB or BAB for conversion, PAS with urgency for retargeting.
- Hot: FAB or 4P for upsell, BAB with a new offer for re-engagement.

Rules that travel with these frameworks: back every promise with verifiable proof, keep one CTA per ad, never over-dramatise the problem (policy disapprovals), never make a before-and-after claim the landing page cannot substantiate.
