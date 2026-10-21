# IronFlock agent skills

A Claude Code plugin with two skills for building on the IronFlock IoT platform:

| Skill | For |
|---|---|
| `ironflock-templates` | IronFlock apps: their architecture, a starter app, and the integration templates in the app's `.ironflock/` folder |
| `ironflock-widgets` | the board widgets themselves: the `@ironflock/widget-*` Lit web components |

## ironflock-templates

Teaches coding agents to build IronFlock apps the way the platform is meant to be
used: containers on every device that keep the app's state in its tables through
the `ironflock` SDK, the board as the app's central UI bound live to those
tables, and web UIs that devices serve themselves, reached through remote-access
tunnels and embedded in the board. It holds:

- the architecture's rules and patterns: where each kind of data goes, how a
  device follows what users set on the board, device functions and topics, what
  the device agent does with a container or a Compose stack, and web UIs on
  devices;
- a starter app, and `new_app.py`, which scaffolds a new app from it: a Python
  program that keeps each device's state and readings in tables, applies the
  settings users save on the board, and serves a live view that the board embeds;
- the rules for writing the integration templates, the files in the app's
  `.ironflock/` folder:

| File | Purpose |
|---|---|
| `board-template.yml` | the app's board: widgets, data bindings, pages, layout |
| `data-template.yml` | the app's tables and transforms in the project database |
| `env-template.yml` | app parameters, delivered as environment variables |
| `port-template.yml` | ports users may open for remote access |
| `ai-template.yml` | the app's AI agents for the IronFlock assistant |

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
/plugin install ironflock@ironflock
```

Or from a shell:

```bash
claude plugin marketplace add IronFlock/agent-skills
claude plugin install ironflock@ironflock
```

Claude Code does not auto-update third-party plugins by default. Turn it on under
`/plugin` → Marketplaces → `ironflock` → Enable auto-update, or pull changes with
`claude plugin marketplace update ironflock`.

To make the plugin available to everyone working on an app, commit this to the
app's `.claude/settings.json`. It loads once a person trusts the folder:

```json
{
  "extraKnownMarketplaces": {
    "ironflock": {
      "source": { "source": "github", "repo": "IronFlock/agent-skills" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "ironflock@ironflock": true }
}
```

The skills trigger on their own: `ironflock-templates` when you work on an
IronFlock app, `ironflock-widgets` when you work on a widget. You can also invoke
them directly as `/ironflock:ironflock-templates` and `/ironflock:ironflock-widgets`.

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
.claude-plugin/marketplace.json          marketplace "ironflock"
plugins/ironflock/
├── .claude-plugin/plugin.json           plugin "ironflock"
└── skills/
    ├── ironflock-templates/
    │   ├── SKILL.md                     workflow and principles
    │   ├── references/
    │   │   ├── app-architecture.md      how an app is built: state, data flow, containers, web UIs
    │   │   ├── board-template.md        board format, data bindings, pages, layout
    │   │   ├── example-board.yml        a complete, valid three-page board
    │   │   ├── widget-catalog.md        which widget for which data (generated)
    │   │   └── app-templates.md         data, env, port and ai templates
    │   ├── assets/app-template/         the starter app
    │   ├── schemas/<name>/v1.yml        JSON Schemas (vendored, see below)
    │   └── scripts/
    │       ├── validate.py              validates a whole .ironflock folder
    │       ├── board_checks.py          the board-specific part of it
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
tests/                                   validator, starter-app and widget-checker regression tests
evals/                                   test app, eval prompts and grader for ironflock-templates
evals/widgets/                           eval prompts, fixtures and grader for ironflock-widgets
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

**Updates reach users by commit.** `plugin.json` sets no `version` on purpose. Users
then track the commit SHA, and every push becomes an update. If you add a `version`,
you have to bump it on every change, or users keep the old copy.

**Test the validator** after changing `validate.py` or `board_checks.py`:
`python3 tests/run.py`. It requires the example board to stay clean and every
mistake in `tests/boards/broken.yml` to be reported.

**Keep the starter app working.** `tests/run.py` also requires
`assets/app-template` to validate without findings, and `new_app.py` to scaffold
an app from it that does too and keeps no trace of the starter's name. The
starter pins its widget versions, `ironflock` and `aiohttp`; when you move a
pin, run the tests, build the image (`docker build` in the starter's folder),
and run the program on a device. Its README.md is written for the people who
install an app, its CLAUDE.md for the agents that change it.

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

**Evaluate the skill** after changing its instructions: run each prompt in
`evals/evals.json` against a fresh copy of `evals/fixtures/machine-monitor`, once
with the skill and once without, then score the runs with
`uv run evals/grade.py <iteration-dir>` (layout: `<eval-name>/<config>/app`). An
eval with `"fixture": null` (`new-app`) starts in an empty `app` folder instead.
Run the skill under test from its files, not from an installed copy of the
plugin, and keep the agent without the skill away from both. On 2026-10-17, after
the architecture guide and the starter app were added, the skill scored 28/28
(the three template evals 18/18 as before, `new-app` 10/10). Without the skill,
`new-app` scored 9/10: the agent worked the architecture out from the SDK's
public sources with twice the tokens and time, but its board had 31 validator
errors (unquoted numeric `layout_id`s, which the board editor does not show, and
numeric route-filter values).

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
```

## License

MIT. See [LICENSE](LICENSE).
