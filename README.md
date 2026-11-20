# IronFlock agent skills

A Claude Code marketplace, `ironflock`, with two plugins for the IronFlock IoT
platform:

| Plugin | For | Skills |
|---|---|---|
| `ironflock` | people who operate IronFlock: projects, devices, apps and their data | none yet (see below) |
| `ironflock-dev` | people who build apps and widgets for IronFlock | `ironflock-templates`, `ironflock-widgets` |

`ironflock-dev` needs `ironflock`. It says so in its `plugin.json`
(`dependencies`), and Claude Code installs `ironflock` with it.

| Skill | For |
|---|---|
| `ironflock-templates` | IronFlock apps: their architecture, a starter app, and the integration templates in the app's `.ironflock/` folder |
| `ironflock-widgets` | the board widgets themselves: the `@ironflock/widget-*` Lit web components |

## The ironflock plugin

The plugin for operating IronFlock holds one skill for now,
`ironflock-dev-moved`: when someone who has only this plugin asks to build an
IronFlock app or widget, it tells them that the build skills moved to
`ironflock-dev` and how to install it. The release that brings the connection
and the first operator skills replaces it. Coming in later releases: the connection to an IronFlock instance, in the cloud or on an
appliance, through the API's MCP endpoint and a key that you enter in
Claude's own settings, so that it works without a shell; and skills to
connect, to look after a fleet of devices and their apps, to query a
project's data, and to use the `ironflock` command where Claude has a shell.
The release-and-deploy loop for app developers will come to `ironflock-dev`.

## ironflock-templates

Teaches coding agents to build IronFlock apps the way the platform is meant to be
used: containers on every device that keep the app's state in its tables through
the `ironflock` SDK, the board as the app's central UI bound live to those
tables, and web UIs that devices serve themselves, reached through remote-access
tunnels and embedded in the board. It holds:

- an interview before a new app or a refactor (how much the user codes, what
  the app is for and gives its users, which entities it deals with, and the
  follow-ups), and the entity model that the tables, the board's lists, forms
  and pages are built from: one entity table per entity, keyed by what
  identifies it, and a list, a "New" form in a dialog and a detail page with
  edit and delete for every entity users manage;
- the architecture's rules and patterns: where each kind of data goes, how an
  entity table's current state and its deletes are read live, how a device
  follows what users set on the board, device functions and topics, what the
  device agent does with a container or a Compose stack, and web UIs on devices;
- a starter app, and `new_app.py`, which scaffolds a new app from it: a Python
  program that keeps each device's state and readings in tables, applies the
  settings users save on the board, and serves a live view that the board embeds,
  and an AI agent that loads an app skill to diagnose a machine;
- a design step for the board: a brief (who looks at it, where, and what each
  page answers), a visual hierarchy, one meaning per colour, three style presets,
  and a wireframe on a design canvas when the agent has one;
- the rules for writing the integration templates, the files in the app's
  `.ironflock/` folder:

| File | Purpose |
|---|---|
| `board-template.yml` | the app's board: widgets, data bindings, pages, layout |
| `data-template.yml` | the app's tables and transforms in the project database |
| `env-template.yml` | app parameters, delivered as environment variables |
| `port-template.yml` | ports users may open for remote access |
| `ai-template.yml` | the app's AI agents for the IronFlock assistant |
| `skills/<name>/SKILL.md` | app skills: instructions an AI agent loads when a task needs them |

The skill gives the agent each template's schema and rules, a catalog of the 24
board widgets, a tool that reads any widget's published configuration schema, and a
validator. The validator catches mistakes the platform would otherwise report only
at install time, or not at all, such as a widget bound to a column that doesn't
exist, or a board page that no click can reach.

## ironflock-widgets

Teaches coding agents to create and change IronFlock board widgets: the npm
packages `@ironflock/widget-*`, whose Lit web components draw the tiles of an
IronFlock board. It holds the rules, standards and guidelines distilled from the 24
existing widgets and from how Studio hosts them:

- the contract with Studio: the properties a widget gets, the events it may send,
  sizing, theming, versions, and the import map of shared libraries;
- standards for the component code, the config schema (`definition-schema.json`
  and its `aiSelection` and `layout` blocks), the default config, the build and the release;
- a starter template, and `new_widget.py`, which scaffolds a new widget repository
  from it;
- `check_widget.py`, which checks a widget repository against those standards.
  `--since HEAD` reports only what a change introduced.

The skill works in a checkout of a widget repository, such as
`ironflock-widgets/widget-gauge`. A new widget also needs changes in IronFlock's
internal platform repositories; the skill points IronFlock developers to the
internal runbook for them.

## Install

In Claude Code:

```text
/plugin marketplace add IronFlock/agent-skills
/plugin install ironflock-dev@ironflock
```

Or from a shell:

```bash
claude plugin marketplace add IronFlock/agent-skills
claude plugin install ironflock-dev@ironflock
```

This installs `ironflock` as well. To operate IronFlock without building apps,
install only `ironflock@ironflock`.

Claude Code does not auto-update third-party plugins by default. Turn it on under
`/plugin` → Marketplaces → `ironflock` → Enable auto-update, or pull changes with
`claude plugin marketplace update ironflock`. The plugins have versions.
Claude Code serves the plugins from the main branch of this repository. A new
install gets what is on main at that moment, including changes that are not
released yet. An installed plugin updates only when its version changes, so
it stays on its version until the next release.
[CHANGELOG.md](CHANGELOG.md) says what each version changed.

To make the plugins available to everyone working on an app, commit this to the
app's `.claude/settings.json`. It loads once a person trusts the folder:

```json
{
  "extraKnownMarketplaces": {
    "ironflock": {
      "source": { "source": "github", "repo": "IronFlock/agent-skills" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "ironflock@ironflock": true,
    "ironflock-dev@ironflock": true
  }
}
```

The skills trigger on their own: `ironflock-templates` when you work on an
IronFlock app, `ironflock-widgets` when you work on a widget. You can also invoke
them directly as `/ironflock-dev:ironflock-templates` and
`/ironflock-dev:ironflock-widgets`.

### If you had the plugin enabled before 1.0.0

Until 1.0.0 there was one plugin, `ironflock`, with the two skills. They moved
to `ironflock-dev`. After the update, `ironflock@ironflock` holds only a short
skill that points to `ironflock-dev`, and you add one line to keep them:

```bash
claude plugin install ironflock-dev@ironflock
```

Or add `"ironflock-dev@ironflock": true` to `enabledPlugins` next to
`"ironflock@ironflock": true`. The skills are now invoked as
`/ironflock-dev:ironflock-templates` and `/ironflock-dev:ironflock-widgets`.

## Requirements

- Python 3.9 or later.
- [`uv`](https://docs.astral.sh/uv/) is recommended. The validator needs PyYAML and
  jsonschema and installs them through `uv run` by itself. Without uv, run
  `python3 -m pip install pyyaml jsonschema`.
- Network access to `registry.npmjs.org` and `cdn.jsdelivr.net` for widget schemas.
  `validate.py --offline` skips the widget checks.
- For widget work: Node.js 24 and npm, as the widget repositories require.
  `check_widget.py` and `new_widget.py` need only Python; the checker's type checks
  use the widget repository's `node_modules`.

## Layout

```text
.claude-plugin/marketplace.json          marketplace "ironflock", plugins "ironflock" and "ironflock-dev"
VERSION                                  the version of the repository and both plugins
CHANGELOG.md                             what each version changed
plugins/ironflock/
├── .claude-plugin/plugin.json           plugin "ironflock"
└── skills/ironflock-dev-moved/SKILL.md  points to ironflock-dev, until the operator skills come
plugins/ironflock-dev/
├── .claude-plugin/plugin.json           plugin "ironflock-dev", needs "ironflock"
└── skills/
    ├── ironflock-templates/
    │   ├── SKILL.md                     workflow and principles
    │   ├── references/
    │   │   ├── app-architecture.md      how an app is built: the interview, entities, state, data flow, containers, web UIs
    │   │   ├── board-template.md        board format, data bindings, pages, layout
    │   │   ├── example-board.yml        a complete, valid three-page board
    │   │   ├── widget-catalog.md        which widget for which data (generated)
    │   │   └── app-templates.md         data, env, port and ai templates, app skills
    │   ├── assets/app-template/         the starter app, with its design/ folder
    │   ├── schemas/<name>/v1.yml        JSON Schemas (vendored, see below)
    │   └── scripts/
    │       ├── validate.py              validates a whole .ironflock folder
    │       ├── board_checks.py          the board-specific part of it
    │       ├── skill_checks.py          the app-skill part of it
    │       ├── widget.py                prints a widget's published schema
    │       └── new_app.py               scaffolds an app from the starter
    └── ironflock-widgets/
        ├── SKILL.md                     workflow and the rules
        ├── references/
        │   ├── host-contract.md         what Studio gives a widget and expects
        │   ├── component.md             standards for the Lit component
        │   ├── config-schema.md         definition-schema.json, default-data.json, aiSelection, layout
        │   ├── repo-and-release.md      layout, build, demo, testing in Studio, release
        │   ├── new-widget.md            scaffolding, first publish, platform registration
        │   └── widget-index.md          the existing widgets, and patterns not to copy
        ├── assets/widget-template/      the starter widget repository
        └── scripts/
            ├── check_widget.py          checks a widget repository
            └── new_widget.py            scaffolds a widget from the template
tools/build_widget_catalog.py            regenerates widget-catalog.md
tools/check_tools.py                     checks the MCP tool names skills use; vendors the catalogue
tools/api/tools.json                     the API's tool catalogue (vendored), api-version.txt its version
tools/release.py                         version, changelog and eval-result checks; writes the version
tests/                                   validator, starter-app, widget-checker and repository-check tests
evals/                                   test app, eval prompts and grader for ironflock-templates
evals/widgets/                           eval prompts, fixtures and grader for ironflock-widgets
evals/results/<version>.md               the eval results of each release
```

## Maintenance

**Schemas are vendored, never edited here.** The canonical files live in
`ironflock-landingpage/public/schemas/` and are published at
`https://ironflock.com/schemas/<name>/v1.yml`. After changing one there, run
`bun run schemas:vendor` in `ironflock-landingpage` (with this repo checked out next
to it), then commit the copies here. `bun run schemas:check` reports drift.

**Widget catalog.** Run `python3 tools/build_widget_catalog.py` when a widget is
added or removed, or when its `aiSelection` text or `layout` changes. The widget list in that
script mirrors the widgets the platform registers. Widget property names are never copied into this repo:
`widget.py` and the validator read them live from npm, so widget releases need no
change here.

**Releases.** The repository has one semantic version, in `VERSION` and in
the `version` of both plugins' `plugin.json` (never in `marketplace.json`).
Claude Code serves the plugins from the main branch of this repository. A new
install gets what is on main at that moment, including changes that are not
released yet. An installed plugin updates only when its version changes, so it
stays on its version until the next release.
A merge without a release therefore reaches every new install at once, under
the old version number, but no existing install; only a release reaches
those. Pinning the marketplace entries to release tags, so that new installs
get released versions only, is the planned next step once the release
workflow sets the tags reliably. Every change goes through a pull request:

- `just merge [TITLE]`: a pull request without a release. Write what changed
  for users under `## Unreleased` in `CHANGELOG.md` in the same pull request.
- `just release-patch` (`-minor`, `-major`): a release pull request. It
  refuses unless `## Unreleased` in the committed `CHANGELOG.md` has content
  and `evals/results/<version>.md` is committed with a result for every skill
  changed since the last release (below). The release writes the version into
  `VERSION`, both `plugin.json` files and the changelog heading. CI checks the
  same on the pull request, and its merge sets the tag `v<version>`.

**The first release.** Before 1.0.0, main has no `VERSION`, so `pr.sh` has no
version to count from and `just merge` refuses the new file. The pull request
that brings 1.0.0 is opened by hand with the title
`release agent-skills v1.0.0` (`gh pr create --base main --title "release
agent-skills v1.0.0"`, then `gh pr merge --squash --auto`). Before it can
merge, it needs `evals/results/1.0.0.md` with the evals of every skill (there
is no earlier release to compare with), and the repository needs its
`release` environment and tag ruleset, as the other IronFlock repositories
have them; without them the tag job of the release fails. After that, every
release goes through `just release-patch` (`-minor`, `-major`).

A major version when people have to change their setup (a skill moves to
another plugin, a plugin is renamed), a minor one for a new skill or ability,
a patch for fixes.

**Eval results in the release.** Evals stay manual, because they cost model
usage, but a release needs their result for every skill whose files changed
since the last release tag. Run them as described below, then write
`evals/results/<version>.md` with one section per changed skill:

```markdown
# Evals for 1.2.0

## ironflock-templates

Result: 31/31 with the skill, 24/31 without (2026-12-01, model and settings).

What the runs showed, and anything that failed and why.
```

`<version>` is the version the release makes (`just release-patch` prints
it). Each section needs a line that starts with `Result:`. `just test` checks
the format of every results file, and the release checks that every changed
skill has its section.

**MCP tool names.** A skill that uses tools of the IronFlock MCP server lists
them in its front matter, under `metadata`:

```yaml
metadata:
  mcp-tools: list_devices check_app_status get_app_logs
```

`just test` (`tools/check_tools.py`) fails on a listed tool that is not in the
API's tool catalogue, and, in a skill with that list, on a tool of the
catalogue that the skill's Markdown names in backticks but the list leaves out.
List every tool a skill mentions. Today's skills list none and are not checked.
The catalogue is vendored in `tools/api/tools.json` with the API version it
came from in `tools/api/api-version.txt`. After an API release, run
`just vendor-tools` in a checkout of this repository next to a checkout of the
API service at that release (or `just vendor-tools <path>`). It takes the
catalogue of the release tag named by the API's `VERSION`, writes both files
and runs the check. Commit them; a renamed or removed tool then fails CI until
the skills follow.

**Test the validator** after changing `validate.py`, `board_checks.py` or
`skill_checks.py`: `just test` (or `python3 tests/run.py`). It requires the
example board to stay clean, every mistake in `tests/boards/broken.yml` to be
reported, and, for app skills, one planted mistake per rule of the release
build to be reported and every limit reached exactly to pass.

**App skills follow the release build.** The platform checks an app's skills
(`.ironflock/skills/`) when it builds a release. `skill_checks.py` repeats
those rules and limits; when the platform changes one, change it there and in
"App skills" in `app-templates.md`. The platform skills that apps may list as
`platform/<name>` are `OPEN_PLATFORM_SKILLS` in `skill_checks.py`, empty while
none is open to apps.

**Keep the starter app working.** `tests/run.py` also requires
`assets/app-template` to validate without findings, and `new_app.py` to scaffold
an app from it that does too and keeps no trace of the starter's name. The
starter pins its widget versions, `ironflock` and `aiohttp`; when you move a
pin, run the tests, build the image (`docker build` in the starter's folder),
and run the program on a device. Its README.md is written for the people who
install an app, its CLAUDE.md for the agents that change it, and its `design/`
folder (purpose, architecture, entities, board, decisions) for both developers
and agents; keep `design/` true to the starter when you change it.

**Test the widget scripts** after changing `check_widget.py`, `new_widget.py` or the
template: `python3 tests/widget_checks.py`. It scaffolds a widget, requires the
finished scaffold to produce no findings, and plants one known mistake per case,
each of which the checker must report. It runs offline and without Node.js. After
changing the template, also build a scaffold for real: `new_widget.py sample --dest
<tmp>/widget-sample`, then `npm install && npm run build` there and
`check_widget.py <tmp>/widget-sample --typecheck`, which then also compares the
generated types with json2ts' output.

**Keep the widget skill in step with the platform.** The template's release
infrastructure (`scripts/`, `.github/workflows/`, `.npmrc`, configs) is a copy of the
fleet's; when the widget repos change theirs, copy the change into
`assets/widget-template/`. `check_widget.py` keeps a snapshot of Studio's import
map (`IMPORT_MAP_SNAPSHOT`) for machines without a Studio checkout next to
`ironflock-widgets/`, and a list of the registered widgets (`KNOWN_WIDGETS`, the
same as `CATEGORIES` in `tools/build_widget_catalog.py`); update both when Studio's
import map or the widget list changes. Calibrate a checker change against the real
widgets: in a checkout with all widget repos, every ERROR the checker reports on
them must be a real defect.

**Evaluate the skill** after changing its instructions, and before every
release that changes it: run each prompt in
`evals/evals.json` against a fresh copy of `evals/fixtures/machine-monitor`, once
with the skill and once without, then score the runs with
`uv run evals/grade.py <iteration-dir>` (layout: `<eval-name>/<config>/app`). An
eval with `"fixture": null` (`new-app`, `camera-app-interview`) starts in an
empty `app` folder instead. An eval with an `answers` field is a conversation:
when the agent asks its questions, answer them from that field and let it
finish; for `camera-app-interview`, also save the agent's first reply as
`QUESTIONS.md` next to `app`, because the grader reads it.
Run the skill under test from its files, not from an installed copy of the
plugin, and keep the agent without the skill away from both. On 2026-10-17, after
the architecture guide and the starter app were added, the skill scored 28/28
(the three template evals 18/18 as before, `new-app` 10/10). Without the skill,
`new-app` scored 9/10: the agent worked the architecture out from the SDK's
public sources with twice the tokens and time, but its board had 31 validator
errors (unquoted numeric `layout_id`s, which the board editor does not show, and
numeric route-filter values). The fifth prompt, `wall-screen-board`, came with the
design step on 2026-10-28 and grades the brief, the preset and the state colours.
On that day it scored 7/7 with the skill and 6/7 without: the agent without it
chose a dark look and consistent state colours by itself, but spread 13 tiles over
the wall screen, label widgets as card headers among them. The sixth prompt,
`records-live`, came on 2026-11-01 with the entity-table rules (the latest and
soft-delete filters show records live, a transform does not) and grades that the
notes list is bound to the table itself with both filters and that no transform
cleans it; it has not been run yet. The seventh, `camera-app-interview`, came
the same day with the interview and the entity model: a vague request the agent
has to ask about first. It grades the first reply for the questions about the
user's coding experience, the app's goal and its entities, and the app for one
entity table per entity, lists bound to those tables with both filters, a "New"
form that opens in a dialog and a delete form (a hidden checkbox on the flag); it has not
been run yet either. The eighth, `app-skill`, came on 2026-11-19 with app skills:
a fault procedure for the app's AI agent. It grades that the procedure is an
app skill listed by the main agent, with a description that says to load it for
a machine in FAULT and instructions that name the app's tables and the warning
level, while the confirmation rule for changing a speed stays in the system
prompt and the prompt names the skill as `app/<name>`; it has not been run yet.

**Evaluate the widget skill** the same way with `evals/widgets/`:
`python3 evals/widgets/grade.py setup <iteration-dir>` clones the fixture widgets
(pinned commits, no `origin` remote), you run each prompt of
`evals/widgets/evals.json` in `<iteration-dir>/<eval>/<config>/` with and without the
skill (telling the agent never to publish, release, commit or push) and save its
report as `REPORT.md` there, and `python3 evals/widgets/grade.py grade
<iteration-dir>` scores the runs. On 2026-10-15 the skill scored 26/26 against
24/26 without it. Agents without the skill did the coding work well, but copied the
fleet's drift into new code: stale scripts and docs, dead schema keywords, and
routing texts too long for the AI's prompt.

**Check the manifests** before pushing:

```bash
claude plugin validate .
claude plugin validate plugins/ironflock
claude plugin validate plugins/ironflock-dev
```

To try both plugins from a checkout, add it as a marketplace:
`claude plugin marketplace add <path to this checkout>`, then
`claude plugin install ironflock-dev@ironflock`. A marketplace added from a
local path loads the files in place, so edits show after `/reload-plugins`.
Remove it again with `claude plugin marketplace remove ironflock`, and add the
GitHub one back.

## License

MIT. See [LICENSE](LICENSE).
