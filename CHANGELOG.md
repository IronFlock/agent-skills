# Changelog

What changed for the people who use the plugins. Write each change under
`## Unreleased` as you make it; the release turns that heading into the
version and its date. Versions follow semantic versioning: a major version
when people have to change their setup, a minor one for new skills or
abilities, a patch for fixes.

## Unreleased

- Apps and boards can read the project's alarms: every project has the built-in app `alarms`, with the tables `alarms` (the current state of each alarm with the latest filter) and `alarm_events` (one row per status change, with its cause, the device and the row that caused it). `ironflock-templates` shows how an app consumes it (`consumes`, `provider_app: alarms` on a board, the SDK's cross-app connection) and its columns; the board validator checks bindings to both tables like the app's own, and reports a write to them, since only the platform writes alarms. The template schemas describe `alarms` and say that `*` includes it. `ironflock-data` and `ironflock-fleet` answer questions about past alarms from `alarm_events` with SQL.

## 1.1.22 - 2026-11-27

- Boards can take photos with a form: widget-form's media field (widget-form 2.3.0 and later) stores several photos per save, each resized to a JPEG, as rows of a photo table linked to the record, optionally with where and when each was taken. `board-forms.md` shows the photo table, the files namespace and the two forms (a report with photos, more photos for an existing record), and the board validator checks the namespace (it must take `image/jpeg`), the accepted image types, the photo table's columns and their types, the link to the record and the photo ID's entity key. The widget skill documents the `media-data-submit` event Studio handles for it.
- Widgets can load a large part that only some configs need on demand: a module loaded with `import()` becomes a chunk next to the bundle, and Studio now imports the bundle by its path in the package, so the chunk is found. The widget skill says when a chunk pays and what it must not do (widget-markdown's code highlighter is the example), and `check_widget.py` follows the chunks in `dist/`: it reports an entry that cannot load alone, a chunk that is missing or imports the entry, and a chunk import that Studio's import map does not provide.
- Every widget takes `lit` from Studio's import map, and `check_widget.py` warns about one that bundles it.
- `check_widget.py` measures a widget's schema and default config as compact JSON, as the IronFlock AI now loads them. widget-form with its media field is about 40,000 of the 60,000 characters and no longer reported as too large.

## 1.1.21 - 2026-11-27

- The plugin directory's check no longer reports the IronFlock plugin as reading the environment and sending it off the machine. Lines in the skills that began with words such as "set" or "export" read to it like shell commands; they are wrapped differently and say the same.

## 1.1.20 - 2026-11-27

- The plugin directory's check no longer reports the IronFlock plugin as sending a credential off the machine. The first pass yield formula in `ironflock-production-figures` read to it like a password-manager command; the formula is worded differently and means the same.

## 1.1.19 - 2026-11-27

- Installing the IronFlock and IronFlock Appliance plugins no longer shows a warning about an unrecognized `privacyPolicyUrl` key. The plugin manifests no longer carry it; the IronFlock README still links the privacy notice.

## 1.1.18 - 2026-11-27

- The widget catalog lists the Toolbar widget, so agents can choose it for a bar of commands, modes, set points or view filters. 1.1.17 added its support before the widget was on npm, when the catalog could not be built for it yet.

## 1.1.17 - 2026-11-26

- Boards can use the new Toolbar widget (`widget-toolbar`): buttons, switches, sliders, choice groups and dropdowns in one bar, each writing its value into a table column and/or setting a URL parameter. The board validator checks the tables and columns its tools write, and a widget that filters on a toolbar's URL parameter is no longer reported as having no source.
- Widget repositories keep their agent guide in `AGENTS.md`, which Claude Code and Codex both read. `check_widget.py` checks `AGENTS.md` instead of warning that `CLAUDE.md` is missing, and asks a repository still on `CLAUDE.md` to rename it. `new_widget.py` creates `AGENTS.md` with the working agreements, plus the settings that enable the IronFlock plugins in Claude Code and Codex.

## 1.1.16 - 2026-11-26

- Building the working copy and looking at the development board need the cloud IDE running. When it is not, Claude passes on the platform's message: open the app in DevStudio, or build a pushed branch. A checkout on a laptop is never built as a working copy.

## 1.1.15 - 2026-11-25

- The plugins moved to `IronFlock/ai-plugins` on GitHub. Add the marketplace with `/plugin marketplace add IronFlock/ai-plugins` (Claude Code) or `codex plugin marketplace add IronFlock/ai-plugins` (Codex). The old address `IronFlock/agent-skills` keeps working, so installed plugins need no change.

## 1.1.14 - 2026-11-25

- The board validator checks edit and delete dialogs opened from a list. It warns when a table's edit column has no URL parameter for its buttons, when no form or widget reads that parameter, when a form opens on a parameter no column sets, and when the form's fields do not show the chosen record.
- The board validator no longer warns about widgets filtered by a switch's URL parameter, and it warns about a switch that sets a URL parameter no widget reads.

## 1.1.13 - 2026-11-25

- The connection skill explains how to select appliance projects for cloud MCP and check a write after an interrupted connection.

## 1.1.12 - 2026-11-24

- In the hosted IDE, “build the app” builds the open working copy on a development device. App logs and status use its DEV run, and build logs follow the device build.

## 1.1.11 - 2026-11-24

- Board templates now guide authors to pad short status pills, wrap explanations, and fit figures to the tile. Related readings share space, and dropdown and calendar filters use compact widths and can blend into the board background.

## 1.1.10 - 2026-11-23

- The CLI skill explains how to sign in to an appliance from a headless terminal using a code and a second device on the LAN.

- **2.0 migration.** The IronFlock connection signs in to the cloud through the browser. Update the plugin and select IronFlock in Claude Code’s `/mcp` or Connect in the plugin’s Connectors tab in Claude chat or Cowork. Review the permissions in Studio.
- If your previous plugin address pointed to an appliance, install the optional `ironflock-appliance@ironflock` plugin in Claude Code, enter its full HTTPS MCP address, and sign in to the appliance. Cloud and appliance sign-ins are independent. The old `api_url` and `api_key` plugin settings are no longer read. You can delete the old key in Studio once you have checked that no script or separate client still uses it.
- For a paired online appliance reached through the cloud, Claude identifies the instance before using its projects or changing a device. This requires an instance that supports and allows cloud access.

## 1.1.9 - 2026-11-23

- Fleet operations use API 2.2.0's `read_app_tool` for developer-marked reads
  and explain changing or unmarked tools before asking for confirmation.
  A refused read is never retried automatically through the changing endpoint.
  Connection guidance explains the separate `apptools:read` and `apptools:write`
  scopes and the read-only preset. The bundled tool catalogue now follows the
  published API 2.2.0 release.

## 1.1.8 - 2026-11-23

- The template validator warns when tools in different agents or in the same
  agent call the same topic with different markings. Equivalent default hints
  do not cause a warning. Template instructions now require titles and markings
  on every topic tool, with eval cases for read, additive and destructive tools.

- A tool in an app's `ai-template.yml` can carry a `title` and `annotations`:
  the four hints of the Model Context Protocol (`readOnlyHint`,
  `destructiveHint`, `idempotentHint`, `openWorldHint`) with its meaning and
  defaults, so that a client can tell a tool that only reads from one that
  changes something. The bundled ai-template schema has them, and
  `references/app-templates.md` explains each hint and when to set it. The
  validator reports annotations on a `delegate:` tool (error), and warns
  about `destructiveHint` or `idempotentHint` next to `readOnlyHint: true`,
  a `topic:` tool without `readOnlyHint` (it then counts as changing
  something and possibly destructive) and `readOnlyHint: false` without
  `destructiveHint` (it then counts as destructive). The starter app's
  `current_reading` tool has a title and is marked read-only.

## 1.1.7 - 2026-11-22

- The app skill has an agent look at the board it built or restyled
  (`references/board-look.md`), with
  `get_dev_dashboard_image` (the app in development, cloud only) or
  `get_dashboard_image` (an installed board; both need API 2.1.2): after a
  new board or a change to a whole page, not after a change to one widget. It
  fixes each widget the report lists as not drawn, runs the five checks on
  the picture and corrects in one round, and tells the user when no picture
  could be had.

## 1.1.6 - 2026-11-22

- Five more looks for boards beside `control-room`, `office` and
  `daylight`: `night-shift` (dim rooms at night, only the alarm bright),
  `showroom` (boards shown on a meeting-room screen or projector),
  `scada-grey` (panels beside grey plant operator screens), `portal` (boards
  embedded in a customer's web portal, in its brand colour) and `lobby`
  (glass tiles over a dark picture the user supplies, with its limit
  stated). Each has its style values, state colours, series colours and
  Delete red, all computed for contrast. The question about the look offers
  at most four viewing situations; `portal` and `lobby` are not among them:
  the user names the brand colour or the picture's address instead. A brand
  colour's label is chosen for contrast, and a brand colour in the hue of a
  state (red, amber, green, or teal where the look's ok is teal) never
  frames the tiles.
  `just test` checks every preset's contrast and style against the board
  schema (`tests/preset_checks.py`).

## 1.1.5 - 2026-11-22

- The app skill points a coding agent to Anthropic's `frontend-design` plugin
  for the design of web pages an app serves itself.
- A board's look: when nothing in the request, the conversation, the app or a
  brand shows who looks at the board and where, light or dark and the brand
  colours, the agent asks the user once, with the presets as choices, and
  takes `office` when the user leaves it open. It says which preset it took
  and why.
- `ironflock-templates` has five checks to run once on a finished or restyled
  board before reporting it (first impression, usability, hierarchy,
  consistency, accessibility), with one round of corrections
  (`references/board-critique.md`, adapted from Anthropic's design plugin
  under the Apache License 2.0; its notice is in the skill's folder).
- Charts on boards: `references/board-charts.md` has the chart rules (chart
  or card, the order of a ranking, scales, how many series, titles and axis
  labels, series colours per preset that hold for colour-blind readers),
  each mapped to the widget setting that applies it; adapted from the data
  plugin's data-visualization skill (Apache 2.0). Series colours are set per
  preset instead of taken from the theme, whose dark theme draws the first
  series red, and a restyle recolours them.
- Boards people act on: `references/board-interaction.md` has the words of
  buttons, forms, delete confirmations, switches, messages and empty tiles,
  touch sizes on tablets and the contrast of controls; adapted from the
  design plugin's ux-copy and accessibility-review skills and the writing
  part of the frontend-design plugin (Apache 2.0). A state shows its word
  beside its colour, text is sized for the viewing distance, the Delete
  button takes the preset's alarm red, and its dialog says what the delete
  does in a section entry (a dialog does not show `subTitle`); the starter
  app follows this.
- `ironflock-production-figures` knows the figures of ISO 22400 and VDMA
  66412 beyond OEE (`references/iso-22400-figures.md` with its SQL): ask
  for the setup ratio (Rüstgrad), technical, allocation or utilisation
  efficiency, first pass yield or the scrap and rework ratio of a machine,
  or which of the standards' figures your data supports.
- Machine builders can ask for the technical availability of their machines
  at customers by VDI 3423, counting only the machine's own faults, and
  compare it with an agreed value (`references/technical-availability.md`
  with its SQL).
- Packaging, filling and bottling lines whose machines report PackML states:
  ask for OEE and stops from those states, line stops by the machine that
  caused them, starved and blocked time, and how a state counts
  (`references/packaging-lines.md` with its SQL; DIN EN 415-11, which
  replaced DIN 8743, and the Weihenstephan Standards named).
- Semiconductor tools with SEMI E10 states: ask for uptime, utilization,
  tool availability, MTBF in productive time and E79 equipment efficiency,
  each with its denominator (`references/semiconductor-equipment.md` with
  its SQL).
- Failures and repairs: ask for the failure count and rate, MTBF, MTTR,
  restoration times, reliability, or planned against unplanned
  maintenance, in the terms of EN 13306, EN 15341 and IEC 60050-192, and
  what machine data cannot show about them
  (`references/maintenance-reliability.md` with its SQL).
- Energy from meters: ask for energy in kWh from counters or power
  readings, energy per part, energy by machine state, base load, load
  profile and peaks, a baseline against output and whether a measure saved
  energy, as ISO 50001 and ISO 50006 describe indicators and baselines
  (`references/energy-performance.md` with its SQL).
- Process quality: ask for a control chart with limits from a baseline, its
  signals and where a process changed, and the capability indices Cp, Cpk,
  Pp and Ppk, as ISO 7870 and ISO 22514 describe them
  (`references/process-quality.md` with its SQL); the drift check of
  `references/root-cause-checks.md` points there.
- `references/oee.md` and `references/downtime-losses.md` name the ISO 22400
  figures they correspond to, as publicly described, and where they differ
  on purpose; they never say a figure conforms to a standard. The rough MTTR
  of the downtime ranking points to the exact one in
  `references/maintenance-reliability.md`.
- Fixed: amounts per period (COUNT, SUM) need a fixed time bucket; the rows
  of a transform reach a widget in reverse order; the "New" button needs
  about 7 × 7 cells; the example board puts the states first and passes its
  own references.

## 1.1.4 - 2026-11-21

- Both plugins have an icon, and `ironflock` names IronFlock's privacy
  notice, in its README and as `privacyPolicyUrl`.

## 1.1.3 - 2026-11-21

- Each plugin has a README of its own, in its folder: what the plugin does,
  what to ask, how to set it up, what it needs, and what it sends, runs and
  fetches.

## 1.1.2 - 2026-11-21

- `ironflock-production-figures` computes its figures correctly in cases
  where it reported wrong ones with confidence: OEE pooled over machines or
  products with different ideal cycle times (quality is now weighted by
  ideal cycle time, so the three parts multiply to the OEE); a machine
  without data or without an input no longer stays in a pooled sum; run
  time, stops and parts count only inside the planned production time, so
  a machine that runs through a break no longer looks better; micro-stops
  are counted as run time as the text says; stops of different stop states
  in a row are one stop, a gap in the data ends a stop, and a stop across
  the start of a period keeps its true start and is counted once; a part
  counter no longer counts an operator's correction, a small jitter, a NULL
  reading or two readings at one time as parts, and a jump to a preset value
  is flagged instead of counted; ratios of whole seconds are no longer 0;
  two states at one time stamp are found and the stop keeps the time; a
  machine stopped for longer than a month still shows as stopped. The German
  term for run time is Hauptnutzungszeit (not Betriebszeit), the ideal cycle
  time is the ideale or theoretische Zykluszeit (a "Soll" value is asked
  about, since it is often the planned one).
- More of the same: a shift in which a machine stood still all the time
  counts as zero parts instead of making the day's OEE not computable; all
  parts and OEE are computed over the planned time that has state data, and
  the time left out is reported beside them; a stop that begins just before
  the end of a period is judged by its whole length, not taken for a
  micro-stop; a shift plan with overlapping shifts or a break outside its
  shift is reported before any figure, and running outside the plan is
  reported apart; quality is still given (by count, said so) when the ideal
  cycle time is missing; a part counter's doubtful steps (a reset, a
  correction, a burst) are counted both ways and reported as a range to ask
  about; a transform refreshed every few minutes no longer reads the whole
  history.
- And: the state at the start of a period is looked for a week back, longer
  than a weekend, so a machine stopped since Friday no longer shows a
  Monday availability of 100%, and a check says when the look-back was too
  short; pooled figures, TEEP and the loss ladder all use the planned time
  that has state data, as the single figures do; parts counted while the
  state was unknown are kept out of performance and reported apart; pooled
  quality falls back to good / total for one product, flagged; a shift whose
  state values are all unmapped is named as such, not as missing data.

## 1.1.1 - 2026-11-20

- New skill `ironflock-production-figures` in the `ironflock` plugin: OEE
  with availability, performance and quality always shown apart, TEEP,
  stops and downtime ranked by minutes and by count, MTTR, MTBF and losses,
  computed in SQL from the rows machines write, and the checks that find
  out why a machine or line stopped, slowed down or made scrap (safety
  first, drift, clustering against a base rate, what changed before, ranked
  causes). Claude asks for what the data does not hold, such as the planned
  time or the ideal cycle time, instead of assuming it, and reports each
  figure with its inputs and period. It works for questions to an instance
  and for an app's transforms and board; `ironflock-data` and
  `ironflock-templates` point to it. Its domain knowledge incorporates
  material adapted from Anthropic's claude-for-manufacturing plugin
  (Apache License 2.0; the three adapted references carry the notice, and
  the licence text travels with the skill).

## 1.1.0 - 2026-11-20

- `ironflock-templates` keeps its board design rules in three references of
  their own: `board-design.md` (the brief, what goes where, one colour for one
  meaning, the look and its three presets), `board-route-tree.md` (the pages
  and routes) and `board-assets.md` (boards that manage assets). The file
  format is split by task as well: `board-bindings.md`, `board-navigation.md`,
  `board-forms.md`, `board-layout-style.md` and `board-markdown.md`, while
  `board-template.md` keeps the basics and the checklist and says which
  references a task needs. Claude reads only those, so a small board change
  is faster and costs fewer tokens. The rules are
  unchanged, with a few additions: a menu placeholder must not share its name
  with a URL parameter a filter sets, a sub-asset route may come from a
  transform only when the table cannot get the parent's key, and a back button
  with an empty route goes one level up, not back in the browser.
- `ironflock-connect` knows that appliances offer the connection from
  IronFlock 1.6.66 on, with keys from the appliance's own Studio, that the
  computer must trust the appliance's certificate, and how to switch the
  plugin between the cloud and an appliance.

## 1.0.0 - 2026-11-20

- Two plugins in the `ironflock` marketplace instead of one. `ironflock` is
  for operating IronFlock: the connection to your instance and the skills
  `ironflock-connect`, `ironflock-fleet`, `ironflock-data` and `ironflock-cli`,
  plus `ironflock-dev-moved`, a short skill that tells people who build apps
  to install `ironflock-dev`. `ironflock-dev` holds the skills
  `ironflock-templates` and `ironflock-widgets` and needs `ironflock`, which
  Claude Code installs with it.
- If you had `ironflock@ironflock` enabled, install `ironflock-dev@ironflock`
  to keep the two skills. They are now invoked as
  `/ironflock-dev:ironflock-templates` and `/ironflock-dev:ironflock-widgets`.
- The plugins have versions now. An installed plugin updates when a new
  version is released. A new install gets the content of the main branch,
  which may hold changes that are not released yet.
- `ironflock-templates` checks an installed release of the app on its devices
  through the `ironflock` plugin's connection: its state, whether its data
  arrives, the app's log and the device's log.
- The `ironflock` plugin connects Claude Code to IronFlock: it declares
  IronFlock's MCP server and asks, when you install it, for the API address
  (`https://api.ironflock.com` by default, `https://api.<domain>` for an
  appliance) and your API key, which Claude Code keeps in the system's secure
  credential store. Change them with `/plugin configure ironflock@ironflock`.
- New skill `ironflock-connect`: how to connect Claude to IronFlock in Claude
  Code, in the Claude app (chat on the web, on the desktop and on a phone) and
  in Cowork, where you add IronFlock as a custom connector with your key as a
  request header; how to create the key in Studio, check the connection, and
  what to do when it fails; and what a key lets Claude do.
- The README has a section "Connect to IronFlock" with the same steps in
  short.
- New skill `ironflock-fleet`: look after a fleet through IronFlock's MCP
  tools. It shows which devices are online and which apps run where, finds out
  why a device or an app does not work in a fixed order and reports the cause in
  plain words, and covers alarms, the apps' own tools and installing, updating,
  stopping and removing apps. Claude reads before it changes anything and asks
  before every change.
- New skill `ironflock-data`: answer questions from a project's data. Claude
  reads the project's tables first, queries with a time range and aggregates in
  SQL, reads the files apps store, and saves a custom transform for a board
  only after you agreed.
- `ironflock-fleet` and `ironflock-data` need version 2.0.0 or later of the
  IronFlock API service.
- New skill `ironflock-cli`: machine work with the `ironflock` command, in a
  client that has a shell (Claude Code). It connects a machine as a new device,
  logs in with an API key from a file or a pipe (never on a command line or in
  the chat), and checks a machine with `status` and `doctor`. Claude asks
  before it installs the agent, deletes a device or works on another machine
  with `--host`, and never prints a `.flock` file, which holds a device's
  credentials. No other skill depends on it.
