---
name: gads-setup
description: Set up a Google Ads account workspace - OAuth and Cloud project API access, MCC access, the first data pull or export normalisation, the brand kit interview, and the brand brain. Use for a new account, "connect Google Ads", "set up the workspace", "brand kit", or when gads validate finds no gads.json.
---

# gads-setup

Load the `gads` skill first. Then work through the gates in order; each one has a check you can see.

## Gate 1 - credentials (once per machine)

Prerequisites the operator supplies: a Google Cloud project with the Google Ads API enabled, an OAuth desktop client JSON downloaded from that project, Explorer access or better for that project (Google Ads API Overview page in Cloud Console), and the manager (MCC) customer id. Since 2026-09-09 API access belongs to the Cloud project that owns the OAuth client; developer tokens were sunset and the API ignores one, so none is needed.

Run:

```
${CLAUDE_PLUGIN_ROOT}/bin/gads auth --client-json <path> --login-customer-id <mcc id>
```

It opens a browser consent, then writes `~/.config/google-ads-playbook/adc.json` and `google-ads.yaml` (mode 600). adc.json also records the OAuth client's GCP project as its quota project (override with `--gcp-project`); use the same project id for the plugin's `gcp_project_id` value. Tell the operator to set the plugin's `adc_path`, `gcp_project_id`, and `login_customer_id` in the plugin config so the bundled MCP can start. An MCP call that fails with `${user_config.adc_path}` in the message means the server did not get those values. Either they are not set (`claude plugin configure google-ads-playbook@<marketplace>` says which), or another `google-ads` server with the same command is shadowing the plugin's: a project `.mcp.json` in the session's folder or a folder above it, such as the root of a google-ads-playbook checkout at 0.2.2 or earlier. `claude mcp get google-ads` shows that server's scope; open the session elsewhere or remove the duplicate.

Check: `${CLAUDE_PLUGIN_ROOT}/bin/gads accounts --login-customer <mcc id>` lists the client accounts. If the API answers CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION (or an authorization error on a production account), the Cloud project has only Test access: stop and send the operator to the Google Ads API Overview page in Cloud Console to apply for Explorer access; nothing downstream will work.

## Gate 2 - data

Preferred: `${CLAUDE_PLUGIN_ROOT}/bin/gads pull --customer <id> --login-customer <mcc id> --workspace ~/gads/<id>` (180 days for campaigns and search terms alike; `--days` and `--search-terms-days` change them).

Fallback when the API is unavailable: the operator exports from the Google Ads UI (Campaigns with the Day column, Search terms, Search keywords, Products, Conversions) and runs `${CLAUDE_PLUGIN_ROOT}/bin/gads normalise <files or folder> --workspace ~/gads/<id>`. It writes the canonical exports and a minimal `gads.json` (the campaign window from the export's dates, source ui). UI exports do not carry the account itself, so add `customer_id`, `customer_name`, `currency` and `timezone` to gads.json with a small edit; Gate 3 adds the brand keys. Merchant Center or Shopify feed export goes to `<ws>/feed.tsv` as supplied.

Check: `gads validate` shows every file with rows and lists the calculators that can run.

## Gate 3 - the brand kit

Copy `${CLAUDE_PLUGIN_ROOT}/references/01-brand-kit.md` to `<ws>/brand-kit.md` and interview the operator field by field. The depth standard applies: a one-word answer is not an answer. Unit economics (AOV, contribution margin, target CAC, break-even ROAS, 90-day LTV) are required before any scaling work. Then record in `gads.json`: `brand_tokens` (brand name, product line names, common misspellings), `target_roas`, and `breakeven_roas` (1 over contribution margin). Write them with a small edit to the JSON, not by hand-typing numbers into a prompt.

Check: `gads leakage` runs without complaining about brand tokens.

## Gate 4 - the brand brain

Run the initialisation prompt from `${CLAUDE_PLUGIN_ROOT}/references/10-prompts.md` Part 0 against the brand kit, the exports, and anything the operator uploaded (reviews in full, product pages, competitor URLs, offer details, sales call notes). Save the answer as `<ws>/brand-brain.md`. Every later skill reads it.

Report: the workspace path, the window pulled, the currency, which gates passed, and what the operator still owes (usually the feed and the reviews).
