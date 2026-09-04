---
name: gads
description: Google Ads playbook router. /gads <precheck|setup|audit|build|feed|creative|manage|bundle> [args]. Alone, shows the workspace state.
---

Load the `gads` skill first (the operating contract). Then route on the first argument:

- no argument: run `${CLAUDE_PLUGIN_ROOT}/bin/gads validate` against `$GADS_WORKSPACE` (ask for the workspace if unset) and report which calculators can run.
- `precheck`: load the gads-precheck skill.
- `setup`: load the gads-setup skill.
- `audit`: load the gads-audit skill.
- `build`: load the gads-build skill.
- `feed`: load the gads-feed skill.
- `creative`: load the gads-creative skill.
- `manage`: load the gads-manage skill.
- `bundle`: run `${CLAUDE_PLUGIN_ROOT}/bin/gads bundle --out <folder or default>` and report the files written.

Pass any remaining arguments through to the skill as the task description.
