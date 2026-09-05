# google-ads-playbook

Audit and rebuild a Google Ads account with the $100M GADs playbook, from inside Claude Code. Read-only by construction: the plugin pulls reports, computes the numbers with tested scripts, and drafts recommendations. You apply them.

## What it does

- `/gads precheck` - should this brand be on Google yet, and the revenue ceiling from Keyword Planner volume.
- `/gads setup` - OAuth once, list the accounts under your MCC, pull 180 days into a per-account workspace, interview the brand kit, build the brand brain.
- `/gads audit` - the six audits with real numbers: branded leakage and true new-customer ROAS, PMax constraint, spend misallocation, campaign roles, conversion tracking, feed.
- `/gads build` - customer language, competitor angles, keyword universe, campaign architecture, RSA copy that passes a hard spec, landing page briefs.
- `/gads feed` - the 10-point feed score and the rebuild list.
- `/gads creative` - the 9-shot arc, the 7 AI formats, prompt files for image and video generation.
- `/gads manage` - daily audit, the 7/14/30-day scaling gate, the ROAS-drop diagnostic order.
- `/gads bundle` - regenerate the claude.ai Project bundle from the same reference files.

## Install

```
/plugin marketplace add juliandickie/google-ads-playbook
/plugin install google-ads-playbook@google-ads-playbook
```

Or from the outfit or loadout catalogs once added: `/plugin install google-ads-playbook@outfit`. The plugin installs disabled; enable it and set its four config values (`/plugin configure google-ads-playbook@outfit`) after the Setup steps below. Requires Python 3.12+, `uv`, and `pipx` (for the bundled Google Ads MCP server).

## Setup

1. In Google Cloud: a project with the Google Ads API enabled and an OAuth desktop client. Download the client JSON.
2. In Google Ads: the developer token from your manager account's API Center (Explorer access or better).
3. Run `gads auth --client-json <file> --login-customer-id <mcc id>`. It writes `~/.config/google-ads-playbook/adc.json` (with the GCP project from the client JSON as its quota project) and `google-ads.yaml`.
4. Set the plugin config (`/plugin` settings): developer token, GCP project id, MCC id, and the absolute path to `adc.json`. The token lives in both places on purpose; rotate both.
5. `gads accounts --login-customer <mcc id>` should list your clients. Then `/gads setup`.

No API access? Export from the Google Ads UI and run `gads normalise`. Everything else works the same.

## Workspace

`~/gads/<customer-id>/` holds `gads.json`, the brand kit and brain, `exports/*.csv` (GAQL column names, money in micros), `feed.tsv`, and `runs/<date>/` with each calculator's markdown and JSON.

## The scripts

`bin/gads` with subcommands `validate`, `normalise`, `leakage`, `misallocate`, `windows`, `feedscore`, `ceiling`, `bundle`, `auth`, `accounts`, `pull`. Stdlib Python except the last three, which run under `uv` with the Google Ads client. Every threshold is a flag; the defaults are the playbook's practitioner numbers, meant to be replaced by the account's own history after 30 days.

`gads pull` defaults to 180 days for both campaigns and search terms, so leakage and misallocate read one window; pass `--days` and `--search-terms-days` to change either (both calculators say which windows they used when they differ). `/gads manage` pulls 70 days on purpose, enough for the 30-versus-prior-30 gate with slack.

## Decisions baked in

Two PMax campaigns (capture and scaling). Non-branded search in Phase 2. Feed descriptions toward 5,000 characters. Scale 20-30 percent every 48-72 hours only when the 7, 14, and 30-day windows agree. They live in `references/02-google-ads-architecture.md`; change them there.

## Credits

Playbook content captured from a public prompt library (see `references/`). The 80-check audit checklist, the conversion tracking method, and the GAQL notes are from AgriciDaniel's claude-ads (MIT). The RSA output spec and the creative strategy layer are adapted from Corey Haines' marketingskills (MIT). Copy School and Webprofits material is distilled, not copied.

## License

MIT.
