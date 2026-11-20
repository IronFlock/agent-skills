# Changelog

What changed for the people who use the plugins. Write each change under
`## Unreleased` as you make it; the release turns that heading into the
version and its date. Versions follow semantic versioning: a major version
when people have to change their setup, a minor one for new skills or
abilities, a patch for fixes.

## Unreleased

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
