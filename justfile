# One version for the repository: VERSION, written into the plugin.json of
# all marketplace plugins and into CHANGELOG.md by the release (tools/release.py). The
# tag is v<version>.
RELEASE_NAME := "ai-plugins"
VERSION_FILE := "VERSION"
VERSION_FILES := "VERSION CHANGELOG.md plugins/ironflock/.claude-plugin/plugin.json plugins/ironflock-dev/.claude-plugin/plugin.json plugins/ironflock-appliance/.claude-plugin/plugin.json"
# PyYAML and jsonschema, the validator's two dependencies, pinned in a
# throwaway environment.
PY := "uv run --no-project --python 3.13 --with pyyaml==6.0.3 --with jsonschema==4.25.1 -- python -I"

# Default recipe: show available commands when `just` is run with no args.
default:
    @just --list

# Lint as CI runs it (non-mutating): ruff.
lint:
    uvx ruff@0.14.0 check .

# The validator's regression tests and the starter app; the MCP tool names the
# skills use against the API's tool catalogue; versions, changelog and the
# form of recorded eval results; the tests of those two checks and of the
# eval runner; and the contrast and file form of the board presets.
test:
    {{PY}} tests/run.py
    {{PY}} tools/check_tools.py
    {{PY}} tools/release.py check
    {{PY}} tests/repo_checks.py
    {{PY}} tests/annotation_evals.py
    {{PY}} tests/preset_checks.py

# Copy the tool catalogue of the API service's current release from a local
# checkout (default ../api) into tools/api/, with its version. Commit both.
vendor-tools API_DIR="../api":
    python3 -I tools/check_tools.py vendor "{{API_DIR}}"
    {{PY}} tools/check_tools.py

# Reload both plugins in the local Claude Code from GitHub: update the ones
# installed, install the ones missing. Running sessions pick them up after
# /reload-plugins or a restart.
refresh-plugin:
    #!/usr/bin/env bash
    set -euo pipefail
    claude plugin marketplace update ironflock
    installed=$(claude plugin list 2>/dev/null || true)
    for plugin in ironflock ironflock-dev ironflock-appliance; do
        if grep -qF "$plugin@ironflock" <<<"$installed"; then
            claude plugin update "$plugin@ironflock" --scope user
        elif [[ "$plugin" != ironflock-appliance ]]; then
            claude plugin install "$plugin@ironflock" --scope user
        fi
    done

# ------------------------------------------------------------------ release --
# Every change reaches main through a pull request whose required checks
# (ci-ok, security / report) are green, squash-merged automatically. The logic
# lives in IronFlock/workflows (scripts/pr.sh at v1); this justfile only names
# the release, checks it and writes the version.
#
#   just merge [TITLE]   a no-release pull request from this feature branch.
#                        The marketplace serves main, so new installs get its
#                        content at once, under the old version number;
#                        existing installs update only on a version change.
#                        (Pinning the entries to release tags is planned.)
#   just release-patch   a release pull request (-minor, -major): the bump
#                        from main's version on top of this branch (or on a
#                        new branch release/v<x> from an up-to-date main). It
#                        refuses without release notes under `## Unreleased`
#                        in CHANGELOG.md, with a badly formed
#                        evals/results/<version>.md, or when
#                        `claude plugin validate` faults a plugin. Eval results are not
#                        required: evals run on demand. Its merge runs
#                        .github/workflows/release.yml, which checks the same
#                        and sets the tag.

# Writes the version (called by pr.sh with the next version); the release
# commit holds exactly VERSION_FILES.
_write-version version:
    python3 -I tools/release.py write {{version}}

# Claude Code's check of the marketplace and the plugins, with the plugin
# directory's submission checks; warnings fail (tools/validate_plugins.sh).
validate-plugins:
    tools/validate_plugins.sh

# Refuses a release without release notes, with a badly formed eval results
# file for the version (tools/release.py), or with a plugin that
# `claude plugin validate` faults. Eval results are optional.
_require-release level: validate-plugins
    git fetch --quiet origin main
    git fetch --quiet --tags origin
    python3 -I tools/release.py gate {{level}}

[positional-arguments]
_pr *args:
    #!/usr/bin/env bash
    set -euo pipefail
    script=$(mktemp)
    trap 'rm -f "$script"' EXIT
    gh api -H 'Accept: application/vnd.github.raw' \
        'repos/IronFlock/workflows/contents/scripts/pr.sh?ref=v1' > "$script"
    bash "$script" "$@"

[positional-arguments]
merge TITLE="":
    just _pr merge {{VERSION_FILE}} "$1"

release-patch: (_require-release "patch")
    just _pr release patch {{RELEASE_NAME}} {{VERSION_FILE}} release.yml {{VERSION_FILES}}

release-minor: (_require-release "minor")
    just _pr release minor {{RELEASE_NAME}} {{VERSION_FILE}} release.yml {{VERSION_FILES}}

release-major: (_require-release "major")
    just _pr release major {{RELEASE_NAME}} {{VERSION_FILE}} release.yml {{VERSION_FILES}}
