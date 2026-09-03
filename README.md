# google-ads-playbook

Scaffold only, 2026-09-04. A read-only Claude Code plugin (namespace `/gads`) that runs the $100M GADs Google Ads playbook against a real account: scripts compute the audit numbers, skills orchestrate, Google's official MCP answers live questions, and one set of references feeds both this plugin and the claude.ai Project bundle.

## What is here now

- `references/01..10` - the canonical knowledge files (brand kit, architecture with locked decisions, Merchant Center standards, copy frameworks with the RSA spec, creative production system, the 80-check audit checklist, conversion tracking method, MCP and GAQL notes, project instructions, prompts in run order).
- `docs/` (gitignored, local) - the approved design spec, the 14-task implementation plan, and the session handoff. Read `docs/SESSION-HANDOFF-2026-09-04.md` first.

Everything else (`bin/gads`, `gads_playbook/`, `skills/`, `commands/`, `.mcp.json`, `.claude-plugin/`, `tests/`) is specified in the plan and not yet built.

## Build status

Not started. Execution is subagent-driven from the plan. This README is replaced by the full one in Task 13.
