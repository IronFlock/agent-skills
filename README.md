# IronFlock agent skills

A Claude Code marketplace, `ironflock`, with two plugins for the IronFlock IoT
platform:

| Plugin | For | Skills |
|---|---|---|
| `ironflock` | people who operate IronFlock: projects, devices, apps and their data | `ironflock-connect`, `ironflock-fleet`, `ironflock-data`, `ironflock-production-figures`, `ironflock-cli` (and `ironflock-dev-moved`, see below) |
| `ironflock-dev` | people who build apps and widgets for IronFlock | `ironflock-templates`, `ironflock-widgets` |

`ironflock-dev` needs `ironflock`. It says so in its `plugin.json`
(`dependencies`), and Claude Code installs `ironflock` with it.

| Skill | For |
|---|---|
| `ironflock-connect` | connecting Claude to IronFlock in the cloud or on an appliance, checking the connection, and what an API key lets Claude do |
| `ironflock-fleet` | devices, the apps on them, alarms, logs and the audit log: what runs where, why something does not work, and changing apps, devices and alarms with the person's agreement |
| `ironflock-data` | a project's data: finding its tables, read-only SQL on the project database, the files apps store, and custom transforms for boards |
| `ironflock-production-figures` | production figures of machines: OEE with availability, performance and quality, stops ranked by minutes and by count, losses, and why a machine stopped; the figures of ISO 22400, technical availability (VDI 3423), packaging lines (PackML), semiconductor tools (SEMI E10, E79), failures and reliability, energy, control charts and capability; for answers from an instance and for an app's transforms and board |
| `ironflock-cli` | machine work with the `ironflock` command in a shell: install the agent, connect a machine as a new device, log in, check a machine (`status`, `doctor`), work on another machine with `--host`; needs a shell, so Claude Code |
| `ironflock-templates` | IronFlock apps: their architecture, a starter app, and the integration templates in the app's `.ironflock/` folder |
| `ironflock-widgets` | the board widgets themselves: the `@ironflock/widget-*` Lit web components |

## The ironflock plugin

The plugin for operating IronFlock connects Claude to an IronFlock instance,
in the cloud or on an appliance, through IronFlock's MCP endpoint and an API
key, and works without the `ironflock` command and without a shell. Its skill
`ironflock-connect` walks a person through the connection on each of Claude's
surfaces, checks it with a first read, and explains what a key lets Claude
do. It states the lowest version of the IronFlock API service it needs
(2.0.0, the first with the MCP endpoint; the API service's own version, not
the IronFlock release).

It also holds `ironflock-dev-moved`: when someone who has only this plugin
asks to build an IronFlock app or widget, it tells them that the build skills
moved to `ironflock-dev` and how to install it.

`ironflock-fleet` looks after the devices and apps of a project: which devices
are online and what runs where, why a device or an app does not work (the
device, then the app's state and data, then its log, the device's log and the
audit log), alarms, the apps' own tools, and changes to apps, devices and
alarms. `ironflock-data` answers questions from a project's data: it reads the
project's tables first, queries the project database (PostgreSQL with
TimescaleDB) read-only with a time range and aggregation, reads the files
apps store, and saves custom transforms for boards. Both read before they
change anything and ask before every change, deletions and paid installs
included. Both need version 2.0.0 or later of the IronFlock API service.

`ironflock-production-figures` computes production figures from the rows
machines write: OEE with its three parts shown apart, stops ranked by minutes
and by count, losses, and the checks that find out why a machine stopped,
slowed down or made scrap. It asks for what the data does not hold (planned
time, ideal cycle time) instead of assuming it, computes in SQL, and reports
each figure with its inputs and period. Its references serve both the
questions people ask an instance and the transforms and boards of apps built
with `ironflock-dev`. Their domain knowledge incorporates material adapted
from the claude-for-manufacturing plugin by Anthropic (Apache License 2.0;
see [License](#license)).

`ironflock-cli` is for machines: where Claude has a shell, it uses the
`ironflock` command to connect a machine as a device and to check it.

Still to come: the release-and-deploy loop for app developers, in
`ironflock-dev`.

## Connect a machine as a device

The `ironflock-cli` skill is for machines, not fleets: it needs a shell on
your own computer or on the machine to set up, so it works in Claude Code
(terminal, IDE extension, Code tab). A sandbox shell in the Claude app or in
Cowork is not that machine. Ask Claude to "connect this machine as
a new device in project X". It checks the machine and your login, tells you
what it is about to do and waits for your yes before it installs anything.
You log in with an API key saved in a file only you can read; the key is
never typed into the chat or onto a command line. For work on the fleet
from anywhere (apps, data, logs, alarms) Claude uses the IronFlock tools of
the connection described above, not this skill.

## Connect to IronFlock

| | |
|---|---|
| MCP endpoint, cloud | `https://api.ironflock.com/mcp` |
| MCP endpoint, appliance | `https://api.<your appliance's domain>/mcp`, once the appliance runs the IronFlock API service, which comes with a later appliance release |
| Authentication | `Authorization: Bearer <API key>`; there is no sign-in through a browser |

Create the key in IronFlock Studio: **Account Settings** > **Developer** >
**API keys** > **Create API key**: choose what the key may do (read only by
default) and where, then **Copy API key**. Studio shows the key only once,
and it is valid for one year. A key that may do everything in all projects
lets Claude do whatever the key's owner may do in IronFlock. Treat the key like a password,
and never paste it into a chat or a file.

**Claude Code** (terminal, IDE extensions, the desktop app's Code tab): the
`ironflock` plugin declares the MCP server. Installing it with
`/plugin install ironflock@ironflock` opens a dialog with two settings: the
API address (`https://api.ironflock.com` by default; for an appliance
`https://api.<its domain>`, without `/mcp` and without a slash at the end)
and the API key, which Claude Code
keeps in the system's secure credential store. Change them later with
`/plugin configure ironflock@ironflock` and restart Claude Code. `/mcp` then
shows `plugin:ironflock:ironflock` as connected. Until the key is set, the
server does not start. An install from a shell (`claude plugin install`) does
not ask; complete it with `/plugin configure ironflock@ironflock` in a
session.

**The Claude app** (chat on claude.ai, in the desktop app and on a phone, and
Cowork): the plugin's own connection works only in Claude Code, so add
IronFlock as a custom connector under **Customize > Connectors** > **Add** >
**Add custom connector**: the MCP endpoint as the URL, authentication
**No sign-in**, and under **Request headers** the header `authorization` with
the value `Bearer <your API key>`. Request headers on custom connectors are a
beta that is available to a limited set of organizations; without them the
Claude app cannot connect to IronFlock. On Team and Enterprise plans an Owner
(on Enterprise also a member whose role includes managing the organization's
libraries) adds the connector under **Organization settings > Connectors**,
and every member then uses that one key. The connector connects from
Anthropic's servers, so the address must be reachable from the internet; an
appliance that only a company network reaches usually cannot be connected
there. For that case Anthropic offers MCP tunnels to Enterprise organizations,
as a research preview on request
([custom connectors](https://claude.com/docs/connectors/custom/add-unlisted)).

Then ask Claude to list your IronFlock projects and a project's devices.
`ironflock-connect` has the details, and what to do when it does not work.

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
install only `ironflock@ironflock`. Claude Code then asks for the IronFlock
API address and key (see [Connect to IronFlock](#connect-to-ironflock)).

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

The skills trigger on their own: `ironflock-connect` when you connect Claude
to IronFlock or the connection fails, `ironflock-fleet` when you ask about
devices, apps, alarms or logs, or why something does not work,
`ironflock-data` when you ask about a project's data or transforms,
`ironflock-production-figures` when you ask for OEE, availability, stops or
downtime, or why a machine stopped,
`ironflock-cli` when you connect a machine as a device or use the `ironflock`
command, `ironflock-templates` when you work on an IronFlock app,
`ironflock-widgets` when you work on a widget. You can also invoke them
directly as `/ironflock:ironflock-connect`, `/ironflock:ironflock-fleet`,
`/ironflock:ironflock-data`, `/ironflock:ironflock-production-figures`,
`/ironflock:ironflock-cli`,
`/ironflock-dev:ironflock-templates` and `/ironflock-dev:ironflock-widgets`.

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
├── .claude-plugin/plugin.json           plugin "ironflock": its settings (API address, key) and the MCP server
├── .claude-plugin/icon.png              the plugin's icon where it is listed
├── README.md                            what the plugin does, its setup and its data; shown where the plugin is listed
└── skills/
    ├── ironflock-connect/SKILL.md       connect, check, what a key lets Claude do
    ├── ironflock-fleet/SKILL.md         devices, apps, alarms, logs, diagnosis, the apps' own tools
    ├── ironflock-data/SKILL.md          tables, read-only SQL, files, transforms
    ├── ironflock-production-figures/
    │   ├── SKILL.md                     which reference for which task, the rules
    │   ├── references/
    │   │   ├── oee.md                   OEE, its three parts and TEEP: inputs, formulas, what each is not
    │   │   ├── downtime-losses.md       stops ranked by minutes and by count, MTTR, MTBF, losses, prices
    │   │   ├── machine-data-sql.md      durations, stops, shifts and counts from machine rows in SQL
    │   │   ├── root-cause-checks.md     why a machine stopped: safety, checks, ranked causes
    │   │   ├── iso-22400-figures.md     ISO 22400 and VDMA 66412 figures beyond OEE
    │   │   ├── iso-22400-figures-sql.md their SQL
    │   │   ├── technical-availability.md technical availability by VDI 3423, for machine builders
    │   │   ├── technical-availability-sql.md its SQL
    │   │   ├── packaging-lines.md       packaging and bottling lines, PackML states
    │   │   ├── packaging-lines-sql.md   their SQL
    │   │   ├── semiconductor-equipment.md SEMI E10 states and E79 figures of fab tools
    │   │   ├── semiconductor-equipment-sql.md their SQL
    │   │   ├── maintenance-reliability.md failures, MTBF, MTTR, reliability, maintenance
    │   │   ├── maintenance-reliability-sql.md their SQL
    │   │   ├── energy-performance.md    energy indicators, baselines, base load, peaks
    │   │   ├── energy-performance-sql.md their SQL, with the traps of meter data
    │   │   ├── process-quality.md       control charts and capability indices
    │   │   └── process-quality-sql.md   their SQL
    │   ├── NOTICE                       origin of the adapted references and what was changed
    │   └── LICENSE-APACHE-2.0.txt       the licence of the adapted references
    ├── ironflock-cli/SKILL.md           machine work with the ironflock command
    └── ironflock-dev-moved/SKILL.md     points to ironflock-dev
plugins/ironflock-dev/
├── .claude-plugin/plugin.json           plugin "ironflock-dev", needs "ironflock"
├── .claude-plugin/icon.png              the plugin's icon where it is listed
├── README.md                            what the plugin does, its setup and its data; shown where the plugin is listed
└── skills/
    ├── ironflock-templates/
    │   ├── SKILL.md                     workflow and principles
    │   ├── NOTICE, LICENSE-APACHE-2.0.txt  the licence of the adapted references
    │   ├── references/
    │   │   ├── app-architecture.md      how an app is built: the interview, entities, state, data flow, containers, web UIs
    │   │   ├── board-template.md        board format basics, which board reference to read for which task, checklist
    │   │   ├── board-design.md          the brief, what goes where, colours, the look and its presets
    │   │   ├── board-route-tree.md      the pages and routes, following the entities
    │   │   ├── board-assets.md          boards that manage assets: lists, forms, detail pages
    │   │   ├── board-bindings.md        data bindings: valueRef, tableRef, filters, aggregation
    │   │   ├── board-navigation.md      page tree, reachability, menus, links, navigation patterns
    │   │   ├── board-forms.md           delete forms and file uploads in the file
    │   │   ├── board-layout-style.md    the grid and the board's style
    │   │   ├── board-markdown.md        widget-markdown cards and HTML
    │   │   ├── board-charts.md          chart rules mapped to widget settings (adapted, Apache 2.0)
    │   │   ├── board-interaction.md     words, touch sizes and contrast of controls (adapted, Apache 2.0)
    │   │   ├── board-critique.md        five checks before reporting a board (adapted, Apache 2.0)
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
tools/release.py                         version, changelog and results-file checks; writes the version
tests/                                   validator, starter-app, widget-checker and repository-check tests
evals/run.py                             runs the evals with and without the skills, grades them, writes SUMMARY.md
evals/                                   test app, eval prompts and grader for ironflock-templates
evals/widgets/                           eval prompts, fixtures and grader for ironflock-widgets
evals/connect/                           eval prompts and grader for ironflock-connect
evals/fleet/                             eval prompts and grader for ironflock-fleet, the MCP configuration of the eval runs, transcript.py (shared with evals/data)
evals/data/                              eval prompts and grader for ironflock-data
evals/cli/                               eval prompts and grader for ironflock-cli, and the stand-in command in fixtures/bin
evals/results/<version>.md               eval results, recorded when someone ran the evals for a version
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
  refuses unless `## Unreleased` in the committed `CHANGELOG.md` has content.
  It needs no eval results; if `evals/results/<version>.md` was recorded, it
  must be well formed (below). The release writes the version into
  `VERSION`, both `plugin.json` files and the changelog heading. CI checks the
  same on the pull request, and its merge sets the tag `v<version>`.

**The first release.** Before 1.0.0, main has no `VERSION`, so `pr.sh` has no
version to count from and `just merge` refuses the new file. The pull request
that brings 1.0.0 is opened by hand with the title
`release agent-skills v1.0.0` (`gh pr create --base main --title "release
agent-skills v1.0.0"`, then `gh pr merge --squash --auto`). Before it can
merge, the repository needs its
`release` environment and tag ruleset, as the other IronFlock repositories
have them; without them the tag job of the release fails. After that, every
release goes through `just release-patch` (`-minor`, `-major`).

A major version when people have to change their setup (a skill moves to
another plugin, a plugin is renamed), a minor one for a new skill or ability,
a patch for fixes.

**Eval results, on demand.** Evals do not run in CI or for every release,
because they cost model usage: run them when you want to measure a change to a
skill. To record a run, write `evals/results/<version>.md` with one section per
skill you evaluated and commit it with the release (or later). The
iteration's `SUMMARY.md` has the `Result:` line of each skill to start from:

```markdown
# Evals for 1.2.0

## ironflock-templates

Result: 31/31 with the skill, 24/31 without (2026-12-01, model and settings).

What the runs showed, and anything that failed and why.
```

`<version>` is the version the results belong to (`just release-patch` prints
the one it makes). Each section needs a line that starts with `Result:`.
`just test` and the release check the format of every results file; neither
requires one.

**MCP tool names.** A skill that uses tools of the IronFlock MCP server lists
them in its front matter, under `metadata`:

```yaml
metadata:
  mcp-tools: list_devices check_app_status get_app_logs
```

`just test` (`tools/check_tools.py`) fails on a listed tool that is not in the
API's tool catalogue, and, in a skill with that list, on a tool of the
catalogue that the skill's Markdown names in backticks but the list leaves out.
List every tool a skill mentions. A skill of `ironflock` that uses tools also
states the lowest version of the API service it needs, as
`min-api-version: 2.0.0` under `metadata`; the check fails without it, on a
value that is not a version, and on one newer than the vendored catalogue's.
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

**Run the evals** with `evals/run.py`. It needs Python 3, uv, git, node and
npm, Claude Code, and an Anthropic API key in the shell: the runs use the key,
never your Claude login, and the runner stops without it. Put the iteration
folder outside every git checkout, so that no agent sees this repository:

```bash
export ANTHROPIC_API_KEY=...
python3 evals/run.py all ~/ironflock-evals/1.0.0
```

`all` runs every eval except cli once with its skill and once without, three
at a time, grades each suite and prints the scores. Each suite gets a folder
in the iteration, in the layout its grader reads (`<suite>/<eval>/<config>/`),
with the grader's output in `GRADES.txt`. `SUMMARY.md` has the scores per
skill, the model, the date, and the cost and run time from the runs' result
events. `python3 evals/run.py <suite> <iteration-dir>` runs one suite
(templates, widgets, connect, fleet, data, cli). `--only <eval>` and
`--config with|without` run single runs, `--model` sets the model, `--jobs`
the runs at a time, and `--dry-run` prints the commands without running them.
A finished run is skipped, so the same command resumes an interrupted
iteration; `--force` runs it again. A run that did not finish starts again
from a fresh copy of its fixture.

Each run is `claude -p` in its own folder, with a Claude configuration of its
own: no CLAUDE.md, memory, hooks, settings, plugins or MCP servers of the
person who runs it, and no npm, GitHub or git credentials. With the skill, it
loads the skill's plugin from this checkout (`ironflock-dev` together with
`ironflock`, which it needs); without, no plugin. The runner checks this in
the init event of each run and stops a run that shows anything else. It does
not use `claude --bare`: that mode leaves the agent only Bash, Edit and Read,
without the Skill tool and the list of skills.

**Evaluate the skill** on demand, when you want to measure a change to its
instructions: `python3 evals/run.py templates <iteration-dir>`. It
runs each prompt in `evals/evals.json` against a fresh copy of
`evals/fixtures/machine-monitor`, once with the skill and once without, and
scores the runs with `uv run evals/grade.py` (layout:
`<eval-name>/<config>/app`). An eval with `"fixture": null` (`new-app`,
`camera-app-interview`) starts in an empty `app` folder instead. An eval with
an `answers` field is a conversation: the runner answers the agent's questions
from that field in a second turn, and saves the agent's first reply as
`QUESTIONS.md` next to `app`, which the grader reads for
`camera-app-interview`. On 2026-10-17, after
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

**Evaluate the widget skill** with `python3 evals/run.py widgets
<iteration-dir>`. It clones the fixture widgets with
`evals/widgets/grade.py setup` (pinned commits, no `origin` remote), runs each
prompt of `evals/widgets/evals.json` in `<eval>/<config>/` with and without the
skill, tells the agents never to publish, release, commit or push (and denies
them `git push`, `npm publish` and `gh`), saves each final report as
`REPORT.md` there, and scores the runs with `grade.py grade`. On 2026-10-15 the skill scored 26/26 against
24/26 without it. Agents without the skill did the coding work well, but copied the
fleet's drift into new code: stale scripts and docs, dead schema keywords, and
routing texts too long for the AI's prompt.

**Evaluate the connect skill** with `python3 evals/run.py connect
<iteration-dir>`. It runs each prompt of `evals/connect/evals.json` once with
`ironflock-connect` and once without, each in an empty folder
`<eval>/<config>/work` without an IronFlock connection, answers no follow-up
question, saves the agent's final reply as `REPLY.md` next to `work`, and
scores the replies with `evals/connect/grade.py`: that the
agent never asks for the key in the chat, does not repeat or store a pasted
key and has it replaced, gives the steps that fit the surface (the plugin's
settings in Claude Code, a custom connector with a request header in the
Claude app and Cowork, an appliance only reachable inside a network), and
reads a 401 and a 429 right. The checks are patterns on the reply; read the
replies too. It has not been run yet.

**Evaluate the fleet and data skills** with `evals/fleet/` and `evals/data/`,
against a local IronFlock test instance with its demo data. Never run them
against a real instance: the prompts ask for deletions, and an agent may carry
them out. The project needs two devices, one online that runs an app and one
offline; that app writes a numeric reading as a time series, has data in the
last 30 days and brings its own tools, one of which only reads; at least one
alarm; and no data about compressors or oil pressure. Set
`IRONFLOCK_EVAL_API_URL` and `IRONFLOCK_EVAL_API_KEY` to the API address and a
key of that local test instance. These names are for the evals only, so that
a shell holding a real address or key cannot point the runs at a real
instance. Then run `python3 evals/run.py fleet <iteration-dir>` and
`python3 evals/run.py data <iteration-dir>` (`all` runs both). The runner
refuses an address whose host is not local (`localhost`, `127.0.0.1`,
`*.localhost`, `*.test`, or a test host named with `--allow-host`). Without
`<iteration-dir>/placeholders.json` it writes one with empty values and
stops: write the names of the demo data into it (the keys are under
`placeholders` in each `evals.json`), then run the same command again;
`python3 evals/fleet/grade.py prompts <iteration-dir>` prints the prompts
filled in. The runner runs each prompt once with the skill and once without,
each in an empty folder `<eval>/<config>/`, connected through
`evals/fleet/mcp.json` alone and with every tool allowed
(`--permission-mode bypassPermissions`), so that the agent's judgement, not a
permission prompt, decides what it calls. It answers no follow-up question.
A run whose init event lists any MCP server besides the eval's own
`ironflock` (the plugin's server, whose default address is the cloud, for
one) fails every check; the runner stops such a run at once, and also one
whose `ironflock` server did not connect. The graders
(`evals/fleet/grade.py grade`, `evals/data/grade.py grade`) score the runs
from the transcript: whether the agent read before it changed anything, asked before
deleting a device or alarms, stopping an app everywhere or installing an app
(with the price from a quote), read the state before the logs and the app's
log before the device's, showed no log lines, changed nothing before the
person's yes, and used the audit log for history; for the data skill, whether it read the schema first, queried only
tables a tool had listed, bounded every query in time, aggregated in SQL,
did not page through history, and chose a query, a widget setting or a
transform as the question needed, asking before it saved one. The checks are
patterns on the tool calls and the reply; read the replies too. Reset the
project to its demo data after an iteration. They have not been run yet.

**Evaluate the cli skill** with `evals/cli/`: it needs no IronFlock instance,
because the runs use a stand-in `ironflock` command, `evals/cli/fixtures/bin`,
on the PATH. Run them only in a throwaway Linux container or virtual machine,
never on a developer's machine and never with bypassPermissions there. The
machine needs Python 3, Claude Code, a checkout of this repository and
`ANTHROPIC_API_KEY`, and no real `ironflock` and no SSH keys. In it, run
`python3 evals/run.py cli <iteration-dir> --in-container`. The runner refuses
without that flag, on macOS, and on a machine with a real `ironflock` or SSH
keys. It puts the stand-in first on the PATH and uses the permission settings
of `evals/cli/evals.json`, which deny `sudo`, `ssh`, `scp`, `curl` and `wget`;
a run that calls any of them, or a real `ironflock`, fails.
`evals/cli/grade.py` reads each run's `TRANSCRIPT.jsonl` and scores the runs.
It has not been run yet.

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

Except: three references of the skill `ironflock-production-figures`,
`oee.md`, `downtime-losses.md` and `root-cause-checks.md`, incorporate
material adapted from the claude-for-manufacturing plugin by Anthropic and
are under the Apache License, Version 2.0. Each says so at its top; the
licence text and the notice of what was changed are in that skill's folder
([LICENSE-APACHE-2.0.txt](plugins/ironflock/skills/ironflock-production-figures/LICENSE-APACHE-2.0.txt),
[NOTICE](plugins/ironflock/skills/ironflock-production-figures/NOTICE)), so
they travel with the installed plugin.
