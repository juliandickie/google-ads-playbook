# Changelog

## 0.1.3 - 2026-09-06

- gads-audit 1.1 diagnoses a zero GA4 import by attribution (all-Direct purchases on a hosted checkout domain mean missing cross-domain measurement) and retires actions imported from dead properties.

## 0.1.2 - 2026-09-05

- gads-audit 1.1 reconciles against the attribution tool and the cart (counts, leads, value) and checks currency conversion in both directions when the account currency differs from the cart's.

## 0.1.1 - 2026-09-05

- `.mcp.json` pins google-ads-mcp to commit 88f0467b9e536c562941fa52a94dd02b193c8fa4 after the live smoke test.
- The gads skill cites the server's real tool names (customers_list_accessible_customers, search_search, metadata_get_resource_metadata).
- `gads pull` defaults to 180 days for campaigns and search terms alike; `--search-terms-days` now follows `--days` unless given. gads-manage keeps 70/70.
- The collapsed-form brand rule applies only to multi-word tokens and tokens of five or more characters, so a short acronym no longer matches inside unrelated words.
- Brand bidding is conditional: the gads contract carries the brand SERP check (organic rank one with no competitor ad means no bid), and audit, build, and manage cite `runs/<date>/brand-serp.md`.

## 0.1.0 - 2026-09-04

First build. Eight skills, the `/gads` router, eleven `bin/gads` subcommands with fixture tests, Google's official MCP bundled through `.mcp.json`, the claude.ai bundle generator. Read-only.
