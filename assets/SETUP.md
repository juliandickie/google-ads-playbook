# Setting Up The Google Ads Project In claude.ai

Ten minutes. Everything you upload is in this folder; everything the brand supplies is listed in step 4.

## 1. Create the Project

In claude.ai, Projects, New project. Name it for the brand (for example "Acme Google Ads"). One Project per brand; swap `01-brand-kit.md` and the brand brain to move the system to a new account.

Model: select Fable 5.1 (or the most capable model available). Extended thinking on.

## 2. Paste the instructions

Open `knowledge/09-PROJECT-INSTRUCTIONS.md`. Copy the whole file into the Project's custom instructions field ("Set project instructions"). This is the operating file: role, load order, rules, diagnostic order, recommendation format, locked decisions.

## 3. Upload the knowledge files

Upload these nine files from `knowledge/` plus `prompts.md`. Keep the numeric prefixes; the instructions reference them by name.

| File | Job |
|---|---|
| 01-brand-kit.md | Fill this in for the brand first (see step 4). Products, margins, offers, target buyer, competitors, tone, banned language, unit economics, voice dials, imagery. |
| 02-google-ads-architecture.md | The account standard, with the decisions locked for this Project at the top. |
| 03-merchant-center-standards.md | Feed standard, title formula, attribute lists, completeness score. |
| 04-ad-copy-frameworks.md | Five headline angles, RSA enforcement spec, six extra frameworks. |
| 05-creative-production-system.md | 9-shot arc, 7 formats, prompt templates, testing framework, concept ranking. |
| 06-google-audit-checklist.md | The 80-control execution checklist under the six audit prompts. |
| 07-conversion-tracking-execution.md | How to prove tracking, under audit 1.1. |
| 08-mcp-and-gaql-notes.md | Optional. Only if the Project reads a Google Ads connector or GAQL exports. |
| 09-PROJECT-INSTRUCTIONS.md | Already pasted in step 2. Upload it too so it is searchable. |
| prompts.md | Every prompt in run order. |

## 4. Upload the brand's own material

The Project performs at the level of the context it is given. Upload all of it, not a sample.

- Product pages and best sellers
- Customer reviews, all of them
- Google Ads performance exports for the last 90 days (campaign, ad group, keyword, product)
- Search terms report for the last 6 months
- Merchant Center feed export
- Competitor URLs
- Meta Ad Library screenshots of competitor creative
- Current landing pages
- Offer details, guarantees, shipping policy
- Brand guidelines and tone of voice
- Objection documents and sales call notes
- Meta account exports if the brand runs Meta (top creatives by CTR, top products by revenue, blended CAC)

Fill in `01-brand-kit.md` before uploading it. Every field is read on every prompt; a one-word answer produces thin output. Unit economics (AOV, contribution margin, target CAC, break-even ROAS, 90-day LTV) are the fields the model cannot work without.

## 5. Run the initialisation prompt

Open `prompts.md`, Part 0. Paste the initialisation prompt. Save the output as `brand-brain.md` and upload it to the Project. Every later prompt reads it.

## 6. Run the 60-minute order

The run order is at the top of `prompts.md`. Six audits, then research, then architecture and copy, then the Merchant Center rebuild. Landing page briefs and creative follow over the next days, then the daily audit runs from that point on.

## What is decided and where to change it

Two PMax campaigns. Non-branded search in Phase 2, not day one. Feed descriptions fill toward 5,000 characters. Scaling 20-30 percent every 48-72 hours behind the 7, 14, and 30-day gate. These live in the "Decisions Locked For This Project" block at the top of `02-google-ads-architecture.md`. Change them there, re-upload the file, and the whole Project follows.

## What this Project will not do

It will not tell you the offer is weak, the margins cannot carry the CAC, or retention makes paid acquisition unprofitable. It executes against the strategy it is handed. If the data says the business itself is the constraint, it is instructed to say so and stop.

## Rebuilding the bundle

The canonical copies of these files live in the google-ads-playbook plugin under `references/`. Run `gads bundle --out <folder>` there to regenerate this folder and the zip. Do not hand-edit the knowledge files here; edit the references and rebuild.
