---
name: gads-setup
description: Set up a Google Ads account workspace - OAuth and developer token, MCC access, the first data pull or export normalisation, the brand kit interview, and the brand brain. Use for a new account, "connect Google Ads", "set up the workspace", "brand kit", or when gads validate finds no gads.json.
---

# gads-setup

Load the `gads` skill first. Then work through the gates in order; each one has a check you can see.

## Gate 1 - credentials (once per machine)

Prerequisites the operator supplies: a Google Cloud project with the Google Ads API enabled, an OAuth desktop client JSON downloaded from that project, the developer token from the manager account's API Center (Explorer access or better), and the manager (MCC) customer id.

Run:

```
${CLAUDE_PLUGIN_ROOT}/bin/gads auth --client-json <path> --login-customer-id <mcc id> [--op-ref "op://..."]
```

It opens a browser consent, then writes `~/.config/google-ads-playbook/adc.json` and `google-ads.yaml` (mode 600). Tell the operator to set the plugin's `adc_path`, `developer_token`, `gcp_project_id`, and `login_customer_id` in the plugin config so the bundled MCP can start. The token is stored twice on purpose (keychain for the MCP, yaml for the CLI); say so.

Check: `${CLAUDE_PLUGIN_ROOT}/bin/gads accounts --login-customer <mcc id>` lists the client accounts. If the API answers that the token is only approved for test accounts, stop and explain the API Center access request; nothing downstream will work.

## Gate 2 - data

Preferred: `${CLAUDE_PLUGIN_ROOT}/bin/gads pull --customer <id> --login-customer <mcc id> --workspace ~/gads/<id>` (90 days, 180 for search terms).

Fallback when the API is unavailable: the operator exports from the Google Ads UI (Campaigns with the Day column, Search terms, Search keywords, Products, Conversions) and runs `${CLAUDE_PLUGIN_ROOT}/bin/gads normalise <files or folder> --workspace ~/gads/<id>`. Merchant Center or Shopify feed export goes to `<ws>/feed.tsv` as supplied.

Check: `gads validate` shows every file with rows and lists the calculators that can run.

## Gate 3 - the brand kit

Copy `${CLAUDE_PLUGIN_ROOT}/references/01-brand-kit.md` to `<ws>/brand-kit.md` and interview the operator field by field. The depth standard applies: a one-word answer is not an answer. Unit economics (AOV, contribution margin, target CAC, break-even ROAS, 90-day LTV) are required before any scaling work. Then record in `gads.json`: `brand_tokens` (brand name, product line names, common misspellings), `target_roas`, and `breakeven_roas` (1 over contribution margin). Write them with a small edit to the JSON, not by hand-typing numbers into a prompt.

Check: `gads leakage` runs without complaining about brand tokens.

## Gate 4 - the brand brain

Run the initialisation prompt from `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md` Part 0 against the brand kit, the exports, and anything the operator uploaded (reviews in full, product pages, competitor URLs, offer details, sales call notes). Save the answer as `<ws>/brand-brain.md`. Every later skill reads it.

Report: the workspace path, the window pulled, the currency, which gates passed, and what the operator still owes (usually the feed and the reviews).
