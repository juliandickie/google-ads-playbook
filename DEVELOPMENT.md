# Development

Handoff file for the next session. A root CLAUDE.md is deliberately absent (it fails `claude plugin validate --strict`).

## Layout

See README. Calculators in `gads_playbook/`, one module each, registered in `registry.py`. Tests in `tests/` with fixtures under `tests/fixtures/` (`ui/` for Google Ads UI exports, `ws/` and `ws60/` for canonical workspaces, `feed.tsv`, `keyword_planner.csv`).

## Run

```
python3 -m unittest discover -s tests -v
claude plugin validate . --strict
./bin/gads --help
```

API subcommands (`auth`, `accounts`, `pull`) re-exec under `uv run --with google-ads --with google-auth-oauthlib`. Set `GADS_IN_UV=1` to skip the re-exec when already inside such an environment.

## Conventions

Money in micros, GAQL column names, one-line stdout summaries, artefacts under `runs/<date>/`, `MissingInput` for anything absent (names the file and the command that produces it). No writes to ad accounts, ever. Text hygiene: no em or en dashes, straight quotes, no colons in headings.

## Live smoke test

Passed on 2026-09-05 against a production client account under a manager account, with a developer token at Explorer access. In order: `gads auth`, `gads accounts`, `gads pull` (180 days, both windows), `gads validate`, brand tokens and ROAS targets written into gads.json, then `gads leakage`, `gads misallocate`, and `gads windows`. Every campaign's 7-day cost, conversions, conversion value, and ROAS in windows.md matched the Google Ads UI to the cent for the same custom range in the account's own time zone. The bundled MCP was driven over stdio at the pinned commit with the exact env contract `.mcp.json` declares (GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_PROJECT_ID, GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID); it exposes `customers_list_accessible_customers`, `search_search` (structured arguments: customer_id, fields, resource, conditions, orderings, limit; it builds the GAQL itself), and `metadata_get_resource_metadata`, and both read calls returned rows. The account-specific record (ids, campaign names, figures) is kept outside the repository on purpose.

Things the live run taught that the fixtures could not: search terms cover well under half of campaign cost on a small account (Google's privacy threshold), so leakage is a floor and says so; a brand acronym of three letters can be absent from every search term while the full brand name matches competitors' names, so choose tokens from the account's actual terms; the Google Ads UI reports in the account time zone, and pull's window end (yesterday in that zone) is what makes the hand-check line up; `get_page_text` on the Google Ads campaigns page returns only the banner, read the grid element instead.

## Live smoke test procedure (repeat on your own account)

In order, eyes on every output. `./bin/gads auth --client-json <oauth desktop client json> --login-customer-id <mcc id>` (add `--op-ref "op://<vault>/<item>/<field>"` to read the developer token from 1Password, otherwise the prompt is hidden and needs an interactive terminal); set the four plugin config values (developer token, GCP project id, MCC id digits only, absolute adc.json path); `./bin/gads accounts --login-customer <mcc id>`; in a fresh session ask the bundled google-ads MCP for customers_list_accessible_customers and one search_search (customer_id, fields [campaign.name], resource campaign, limit 5), or, without an installed plugin, drive the server over stdio with the .mcp.json env; `./bin/gads pull --customer <id> --login-customer <mcc id> --workspace ~/gads/<id>`; `./bin/gads validate`; add brand_tokens, target_roas, breakeven_roas to gads.json; `leakage`, `misallocate`, `windows`; compare one campaign's 7-day cost and conversions in windows.md with the Google Ads UI for the same custom range (they must match to the cent; the UI uses the account time zone); keep the account-specific record outside the repo; commit.

## Rulings made during the build

Behaviour that differs from the original plan text, decided during the subagent-driven build on 2026-09-04. Each is a small, reversible choice.

- normalise parses UI exports in memory and never writes a temp file beside the source export; it validates required columns even on header-only exports; a folder with a bad export writes nothing (two-phase); unknown exports and missing paths fail with the file named.
- Brand classification treats hyphens and underscores in campaign names as word boundaries and never classifies a campaign from other campaigns' keywords.
- leakage and misallocate print the campaign window and the search-terms window they mix and say when they differ; misallocate's share denominator is the campaign's summed search-term cost (window-consistent) and its Coverage section shows reported campaign cost beside it; winners rank by conversions, losers by cost.
- windows renders an Account rollup, judges window availability per campaign from that campaign's own first date, requires the budget-lost and rank-lost columns, and prints the 7-day rank-lost share the manage diagnostic cites.
- ceiling validates the keyword, volume, and bid columns (bid columns optional only with both CPC overrides) and honours GADS_WORKSPACE like every other subcommand.
- bundle zips only the files it wrote and names stale leftovers in knowledge/ without deleting them.
- pull is two-phase (all queries, then all writes); every API failure names the query, quotes Google's error, and lists the two likely causes (developer token access level, login customer id); auth wraps 1Password op read failures and creates credential files as 0600 from the first byte.
- Brand.from_workspace, unknown exports, and missing inputs all raise MissingInput so every CLI failure is one clean line and exit 2.
- Final review fix wave (2026-09-04): leakage only splits SEARCH/SHOPPING/empty-channel campaigns by search terms (everything else is kind "other-channel", its own markdown section, excluded from the non-brand grouping and true new-customer ROAS but still in the account total); a campaign present in search_terms.csv but absent from campaigns.csv is kind "terms-only" and excluded from every account total; other_cost is None ("n/a (windows differ)") rather than a misleading number when the campaign and search-terms windows differ. misallocate's share denominator is the campaign's reported cost (campaigns.csv) when the windows match or are unknown, falling back to term cost for a campaign absent from campaigns.csv or when the windows differ ("share_basis" in the result says which; the winner/loser row key is "campaign_basis_cost"). gads-manage pulls 70/70 instead of 60/60. feedscore.render_md caps the product table at top_n ranked plus top_n lowest-scoring (with a "and K more in feedscore.json" line and a score distribution), and lists products.csv ids missing from the feed with their revenue. pull computes the window end as yesterday in the account's own time zone (zoneinfo, falling back to the local date with a "window_note" when the zone is empty or unknown) and blanks the three search impression-share fields on non-SEARCH/SHOPPING campaign rows. auth and pull both strip dashes from every customer id before writing or using it; make_client wraps a GoogleAdsClient.load_from_storage failure into MissingInput naming the yaml path. accounts drops the level <= 1 filter (still selects and prints level) so sub-manager accounts are not hidden. cli.py imports and calls registry.register_all unconditionally (no more silent ImportError swallow). windows treats a zero-cost window as unknown, not "below break-even" (hold reason "no spend in the L-day window", never a false cut), and raises MissingInput naming the campaign if all its rows lack segments.date. io.sniff_delimiter decides tab versus comma everywhere the plugin reads a header line, used by read_csv_lines, read_header, and normalise's own header-line search (which now parses with csv.reader instead of a bare comma split); read_csv and read_header use splitlines(keepends=True) so a quoted field's embedded newline survives.
- Residuals from the final review closed on 2026-09-04: terms-only and other-channel rows show n/a for unattributed cost; misallocate rows carry campaign_basis_cost; pull's channel set renamed IMPRESSION_SHARE_CHANNELS; normalise keeps quoted newlines and recognises tab exports without a title line; test output is pristine.
- Brand bidding is conditional (2026-09-05, maintainer rule): a brand term is bid only where the brand is not already first organically in that country or a competitor ad shows on the page. The check lives in the gads contract as the brand SERP check (DataForSEO `serp_organic_live_advanced` when available, manual otherwise) and writes `runs/<date>/brand-serp.md`; audit, build, and manage read it. This qualifies the library's first mistake, which stays as written in references/.
- auth writes quota_project_id into adc.json from the OAuth client JSON's project_id (override with --gcp-project) so ADC consumers such as the bundled MCP have a quota project.

## State at the end of the smoke test and publish session (2026-09-05)

The live smoke test passed (section above). The repository is public at https://github.com/juliandickie/google-ads-playbook (main, pushed 2026-09-05) and listed in the outfit and loadout catalogs; `claude plugin install google-ads-playbook@outfit` installs 0.1.0 into the plugin cache, disabled by default with the four userConfig values unset. Before the first push the history was rewritten so no client account record ever appears in it (the tracked DEVELOPMENT.md was dropped from every earlier commit and re-added scrubbed; a GCP project id, a 1Password item path, and a brand name in tests and help text were replaced in place). 141 tests pass; strict validation passes; `.mcp.json` is pinned. Still not exercised: the in-host MCP start (enable the plugin, set the four values with `/plugin configure google-ads-playbook@outfit`, start a fresh terminal session, call customers_list_accessible_customers). Next after that: the first real `/gads audit`.

Publishing rule for this repo: account-specific material (customer ids, manager ids, GCP project ids, campaign names, spend and conversion figures, vault paths) never goes into a tracked file. Keep it under `docs/` (gitignored) and write generic notes here.

## State at the end of the build session (2026-09-04)

Tasks 1 to 13 of the plan plus the whole-branch final review and its fix wave are committed on main; 132 tests pass; strict validation passes. Nothing has run against a real account. The session handoff with every ruling lives in `docs/` (local only). The two catalog repos (`~/code/plugins`, `~/code/ai-loadout`) hold the marketplace entry and README row staged, not committed.

## Lessons from the first real audit (2026-09-05, generic)

- Marketplace updates are version-gated. `claude plugin update` reports "already at the latest version" until `.claude-plugin/plugin.json` and `marketplace.json` carry a new version, whatever main holds. Bump the version with every change that should reach installed copies.
- The exports do not carry settings. The first audit needed campaign network and geo settings, criteria, shared negative lists, ads with strength and policy topics, assets, audiences, conversion goals, quality components, landing pages, device and geo splits, and change events; all came from the bundled MCP's `search_search` over stdio and were saved under the workspace `raw/`. Candidate feature: `gads pull --deep` writing those as JSON so the audit skill can cite them.
- GAQL through `search_search`: `DURING LAST_90_DAYS` is rejected (LAST_30_DAYS works; use `segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'` for anything else); `campaign_asset` and `ad_group_asset` need `campaign.status` in the field list when it is filtered; `change_event` needs a BETWEEN range of 30 days or less; `conversion_action` reports `metrics.all_conversions`, not `metrics.conversions`; `campaign.start_date` is not selectable. Rows come back with flat dotted keys (`campaign.name`), and nested RSA headline objects carry enum ints.
- The biggest finding was in a per-action volume query, not in the exports: which conversion actions actually fired in the window. `conversion_actions.csv` shows configuration only; add `metrics.all_conversions` per action to the pull or the deep pass.
- A conversion audit is not finished until it is reconciled with the attribution tool and the cart for one window (counts, leads, value). When the account currency differs from the cart's, check that uploaded values are converted in and that the attribution tool converts spend in; a tool that shows the account-currency spend to the cent as its own currency is not converting.
- A GA4 import that records zero is usually an attribution fault, not a link fault: if the property records purchases but every one is Direct by session and first-user source and they fire on a hosted checkout domain, cross-domain measurement is missing. Google's analytics-mcp answers this in three reports (links, events by name, purchases by source); the Data API must be enabled separately from the Admin API.
- A conversion audit needs the biddable goal categories (`customer_conversion_goal`, `campaign_conversion_goal`) beside `primary_for_goal`; a primary page-view action in a non-biddable category does nothing, a primary signup in a biddable one drives every Maximize Conversions campaign.

## Known gaps

- The collapsed-form brand rule (spec 6.2) now applies only to multi-word tokens and tokens of five or more characters (decided 2026-09-05); short tokens match as whole words only, so a three-letter acronym no longer matches inside unrelated words.
- gads pull defaults to 180 days for both campaigns and search terms (decided 2026-09-05; it was 90 and 180), search terms following `--days` unless `--search-terms-days` is given; leakage and misallocate still state the two windows in case they differ. gads-manage pulls both at 70 days on purpose (30-versus-prior-30 plus slack).
- gads-precheck (the 22 signs) and gads-audit (the five mistakes) cite the captured library at ~/code/google-ads-audit-prompt-library, which only exists on this machine; the audit skill names the five mistakes inline, the precheck skill does not carry the 22 signs.
- feedscore lists products.csv ids that are absent from the feed (closed in the final review wave); a feed with duplicate item ids across variants still scores each row separately.
- PMax search terms come only from a manual insight export. Search terms exclude Google's low-volume terms; leakage is a floor. Locales beyond en-AU and en-US number formats are untested. The MCP server is pinned to google-ads-mcp commit 88f0467b9e536c562941fa52a94dd02b193c8fa4 (2026-09-05); bump the pin deliberately, and re-run the stdio check when you do, because tool names changed between the spec and this commit.
