# Changelog

What changed for the people who use the plugins. Write each change under
`## Unreleased` as you make it; the release turns that heading into the
version and its date. Versions follow semantic versioning: a major version
when people have to change their setup, a minor one for new skills or
abilities, a patch for fixes.

## Unreleased

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
