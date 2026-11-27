#!/usr/bin/env bash
# Claude Code's own check of the marketplace and of every plugin in plugins/:
# `claude plugin validate --strict`, so an unrecognized field or missing
# metadata fails, and for each plugin also the plugin directory's submission
# checks (--profile directory). Part of the release: `just release-*` runs it
# before the release pull request, release.yml on that pull request and on its
# merge.
#
# CLAUDE names the command, default `claude`; release.yml sets it to a pinned
# @anthropic-ai/claude-code from npm.
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -a claude <<<"${CLAUDE:-claude}"

"${claude[@]}" plugin validate --strict .
for plugin in plugins/*/; do
    "${claude[@]}" plugin validate --strict --profile directory "$plugin"
done
