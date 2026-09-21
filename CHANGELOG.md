# Changelog

## 0.2.0 - 2026-09-22

- `gads audit` writes the audit report itself: `runs/<date>/audit.md` in the document layout, `audit.json`, and with `--executive` a two-page `audit-executive.md` for the client owner. It reads whatever the workspace holds (exports, the three calculator runs, the deep pass, the brand SERP check and reconciliation from this or the latest earlier run) and names every missing source; controls those sources would have decided read "no evidence". Recommendations are rule-drafted with all twelve fields and marked draft for the gads-audit skill to review. The 06 checklist walk names every control from the shipped reference.
- gads-audit runs `gads audit --executive` first and reviews the drafts instead of composing the report by hand.
## 0.1.5 - 2026-09-21

- gads-audit report shape is a document: a heading per section and per recommendation, one labelled fact per line with a blank line between, no bullets or tables in the body, and every cited file a clickable link that resolves (absolute `file://` for workspace files, GitHub URLs for references). The gads contract carries the same rule for every report the skills write.
## 0.1.4 - 2026-09-15

- `gads pull --deep` runs the settings deep pass after the exports (`--deep-only` runs it alone): 25 read-only queries written as one JSON file each under `raw/deep-<date>/` with a `manifest.json`, covering campaign settings and criteria, shared and ad-group negatives, ads with policy topics, assets, audiences and user lists, conversion goals, conversion actions with per-action volumes and a per-campaign per-action split, keyword quality components, landing pages, device and geo splits, and 28 days of change events. Enums are written by name. A query the API rejects writes `<name>.error.txt` and the pass carries on; the stdout line names every failure and the exit code is 1 when any query failed.
- gads-audit cites the deep pass files as evidence and writes the report one line per recommendation field, checklist control and sub-point.
- gads-audit's currency check can be settled from data: match a few cart orders against the values the account recorded by click date.
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
