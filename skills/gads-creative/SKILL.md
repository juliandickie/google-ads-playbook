---
name: gads-creative
description: YouTube and Demand Gen creative production - concept ranking, the 9-shot villain arc, the 7 AI ad formats, image and animation prompts, Meta repurposing, the 4-week test. Use for video ads, YouTube, Demand Gen creative, ad concepts, or any Part 3 prompt.
---

# gads-creative

Load the `gads` skill first. Needs `brand-kit.md` (hex codes, imagery, voice dials) and `research/customer-language.md` from gads-build. Reference `05-creative-production-system.md` in full, including its strategy layer.

## Before producing anything

Rank concepts by evidence tier (own-account winner, customer verbatim, 60-day competitor creative, organic engagement, cross-niche pattern, hunch). Hunches ship low-fidelity first. Pick the format from the selection framework in `05` by product type, funnel stage, and budget, and state the choice.

## Production (prompts 3.1 to 3.5 in `references/10-prompts.md` Part 3)

1. 3.1 concept: the 9-shot arc with the villain that is never the customer. Fill the Style bracket with the chosen format.
2. 3.2 static prompts per shot, with the brand hex codes from the kit and exact on-screen text.
3. 3.3 animation prompts per frame.
4. Generation: hand the prompts to creators-studio (`/create-image generate` for stills, `/create-video` for animation) when installed. Inspect every generated image before using it. Otherwise deliver the prompt files for the operator's tool of choice.
5. 3.4 concept multiplier: five concepts, one pain point and funnel stage each.
6. 3.5 Meta repurposing for 6, 15, and 30-second cuts when Meta winners exist.

## Testing

Set up the 4-week framework from `05` (five concepts equal budget, kill bottom two, hook variants, style variants, scale the winner) and the hook diagnostic funnel for reading results. One component per iteration.

Save concepts and prompts under `<ws>/creative/<concept>/`. Report: the format chosen and why, the ranked concept list with evidence tiers, and what was generated versus what awaits the operator.
