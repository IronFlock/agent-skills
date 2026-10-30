---
name: ironflock-templates
description: Build IronFlock apps: their architecture (edge containers that keep all state in the app's tables through the ironflock SDK, the board as the central UI, device web UIs embedded through remote-access tunnels), a starter app to scaffold, and the integration files in the app's .ironflock/ folder, with a validator. These are board-template.yml (the board: widgets, data bindings, pages, layout), data-template.yml (tables and transforms), env-template.yml (parameters), port-template.yml (remote-access ports) and ai-template.yml (AI agents). Use this whenever you create, design or change an IronFlock app or its edge code, add or change a board, dashboard or widget, bind a widget to live data, add a table or column, expose a parameter or port, or define an app's AI agent. Also use it when the user mentions IronFlock, Reswarm or a .ironflock folder, even if they don't say "template". To change a widget's own code (the @ironflock/widget-* packages), use ironflock-widgets instead.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*), Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/*)
---

# IronFlock apps and their templates

An IronFlock app is a container, or a Docker Compose stack, that runs on every
device the app is installed on, plus a `.ironflock/` folder that plugs it into the
platform. The containers talk to the platform only through the `ironflock` SDK,
and keep the app's state in its tables. The board, the app's central UI, is bound
to the same tables live, so the edge code and the UI never call each other. A web
UI that a container serves itself is reached through the port's remote-access
tunnel and embedded in the board.
[references/app-architecture.md](references/app-architecture.md) has the rules,
and `assets/app-template/` is a starter app that follows them.

When a user installs the app in a project, the platform reads the `.ironflock/`
files. Each file is optional and independent:

| File | What the platform does with it |
|---|---|
| `data-template.yml` | Creates the app's tables in the project's database. The app fills them through the SDK. |
| `board-template.yml` | Installs the app's board (dashboard): widgets bound to those tables, laid out on pages. |
| `env-template.yml` | Renders a parameters form per device or device group. Values reach the app as environment variables. |
| `port-template.yml` | Lists the ports the app serves. A production install opens a remote-access tunnel for each. |
| `ai-template.yml` | Registers the app's AI agents with the IronFlock assistant. |

Each file has a JSON Schema in `${CLAUDE_SKILL_DIR}/schemas/<name>/v1.yml`, the same
file that is published at `https://ironflock.com/schemas/<name>/v1.yml`. Every field
in it is described.

## Workflow

1. **Read before writing.** Look at the existing `.ironflock/` files and at the app's
   code. The code shows what the app actually publishes (`publish_to_table` calls)
   and which functions it registers (`register_device_function` calls). The templates
   have to agree with it. If templates already exist, run the validator (step 6)
   once before changing anything, so you can tell findings that were already there
   from ones you introduce. Before you design an app, write its edge code or change
   how its parts talk to each other, read
   [references/app-architecture.md](references/app-architecture.md).
2. **Start a new app from the starter.** For a new app in an empty folder (or one
   holding only `.git`), scaffold it:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/new_app.py <app-name> --dest <dir>
   ```

   `<app-name>` is the app's name in IronFlock. The copy is a working app: a
   program that reads a machine (simulated) on every device, keeps each device's
   state and readings in tables, applies the limit users set on the board, and
   serves a live view that the board embeds. Keep its structure and replace its
   example: the data source in `read_machine()`, the tables, the board, the live
   view, and the `TODO:` texts in `README.md` (the app's description for its
   users) and `CLAUDE.md`. Delete what the app does not need, such as the live
   view and the port-template when it serves no web page. Never scaffold over an
   existing app, including the demo app IronFlock puts into a new app's
   repository: use the starter's files as the reference for changing the app's
   own, and ask before replacing demo code.
3. **Data comes first.** A board can only show what a table in `data-template.yml`
   holds. Design or extend the tables before the board. If the code doesn't publish
   the data yet, say so and change the code too. For each table, decide whether
   users of the app should work with it directly. Mark tables that only hold the
   app's internal details `private: true` (app-templates.md explains when).
4. **Design the board before you write it.** Read "Designing a board" in
   [references/board-template.md](references/board-template.md). Decide who looks
   at the board and where, what question each page answers, what people look for
   first, and which look (a preset in its Style section) suits that viewing
   situation, `office` when nothing says otherwise. Write those decisions into
   the board's comment header. When the
   user wants to see the board before it exists and your environment has a design
   canvas (in Claude Code, the Artifact tool's Design type), sketch the pages as
   wireframes there first, as that section describes. Otherwise write the band
   plan in text and go on.
5. **Write the file.** For the board, read
   [references/board-template.md](references/board-template.md) and the complete
   example [references/example-board.yml](references/example-board.yml) first,
   choose widgets with [references/widget-catalog.md](references/widget-catalog.md),
   and look up each chosen widget's exact properties (see below). For the other four
   files, read [references/app-templates.md](references/app-templates.md) and the
   file's schema.
6. **Validate, fix and repeat until there are no errors:**

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py <app-dir>
   ```

   It checks every template against its schema, the rules the platform otherwise
   reports only at install time, and each board widget against the widget's
   published schema. Each finding names the file, line and path. If it reports a
   missing module, run it as `uv run ${CLAUDE_SKILL_DIR}/scripts/validate.py <app-dir>`,
   or install `pyyaml` and `jsonschema`. Warnings are judgment calls. Read each one
   and fix it unless it is deliberate. The validator has its own test suite, so a
   clean run is enough; there is no need to seed mistakes to test it.
7. **Report** what you created, which look you chose and why, which tables and
   widgets connect, and anything the app's code still has to do. Tell the user
   they can open the board in IronFlock's board editor to adjust it visually. The
   editor reads and writes the same `board-template.yml`. For a new app, add how
   to get it running: push it to the app's repository in IronFlock and run it on
   a device from the IDE. That development run gets a private tunnel for each
   http(s) port, which its developers open from the IDE's side menu; the URLs the
   board embeds come with a production install.

## Widget schemas

Every widget is an npm package whose `definition-schema.json` defines exactly what its
`chartconfig` may contain. Read it before configuring the widget, because property
names differ between widgets and change between releases:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/widget.py widget-linechart            # outline of all properties
python3 ${CLAUDE_SKILL_DIR}/scripts/widget.py widget-linechart --path dataseries
python3 ${CLAUDE_SKILL_DIR}/scripts/widget.py widget-linechart --example  # a working config
python3 ${CLAUDE_SKILL_DIR}/scripts/widget.py widget-scada --symbols tank      # find SCADA symbols
python3 ${CLAUDE_SKILL_DIR}/scripts/widget.py widget-scada --when symbol=cylindrical-tank
```

The outline marks `dataDrivenDisabled` (cannot be bound to data), enums, defaults and
conditional fields. `--example` prints plain values. In a board template the same
config needs the literal prefixes and data references described in board-template.md.

## IronFlock documentation

This skill covers the templates and how an app is built. For the rest of the
platform, look things up in the documentation at <https://ironflock.com/en/docs/>.
Don't answer from memory, because the platform changes faster than your training
data. Look it up when the task or the user's question involves:

- an SDK function, its options or its errors beyond what app-architecture.md shows,
  or the REST API;
- what users do in IronFlock: projects, connecting devices, installing apps, app
  settings, updates, privileges, alarms, boards in Board Studio, the AI assistant;
- remote access, tunnels, SSH and host access;
- developing and shipping an app: the cloud IDE, Git integration, releases, the App
  Store, pricing and billing;
- file storage, network shares, data from other apps, LoRaWAN, the collector apps;
- deployment options (cloud, appliance, private cloud), proxies, certificates,
  security and access control.

How to look something up:

1. Fetch <https://ironflock.com/llms.txt>. It lists every English docs page in
   sidebar order, each with a one-line description and a link to the page's
   Markdown.
2. Fetch the Markdown of the pages that match. Any docs URL has one: drop the
   trailing slash and add `.md` (`…/docs/app-development/data-backend/` →
   `…/docs/app-development/data-backend.md`). Links inside it point to other
   pages' Markdown.
3. When you pass on something from the docs, give the user the page's URL (the
   same path with its trailing slash, without `.md`).

For the syntax of the `.ironflock/` files, this skill's schemas and the validator
are authoritative. The docs explain what the files do, but some of their examples
lag behind, for instance older ones that omit required fields. If the docs and
this skill disagree on a template, follow the skill and mention the difference.
For SDK signatures, the SDK page links each SDK's README on GitHub, which is the
complete reference.

## Principles

- **Keep the app's state in its tables.** Devices write what they measure and the
  state they are in, the board writes what users decide, and each device follows
  that with `subscribe_to_table`, which also delivers what was saved while the
  device was offline. Neither side calls the other, nothing polls, and app code
  never touches the SDK's connection or sessions. app-architecture.md has the rules
  and the code patterns.
- **Reach a device's web UI through its tunnel.** Declare the port in
  port-template.yml, write the URL from `getRemoteAccessUrlForPort` into a table,
  and bind widget-embed to it. Never hard-code a device's address, port or URL.
- **One colour, one meaning.** The chosen preset's four state colours mark ok,
  warning, alarm and idle, with the same value on every widget. The board's chrome
  stays neutral and nothing else is coloured. board-template.md, "Designing a
  board", has the rules and the key each widget takes its colours from.
- **Bind, don't paste.** If a value lives in a table, bind the widget to it with a
  data reference. Pasted numbers go stale the moment the board is installed.
- **Make every page users see reachable by clicking, and the way there obvious.**
  People only click through a board; nobody types a route. Every page with widgets
  must be reachable from the home page and lead back to it. A page that only holds
  the pages below it (`/devices` above `/devices/*`, with `gridLayout: []`) need
  not be reachable itself, as long as those pages are. Home is a menu's title,
  never a menu item: an item is highlighted whenever the current route starts with
  its route, so an item for `/` is highlighted on every page. board-template.md's
  "Pages and navigation" section has the rules and the patterns (sections, list and
  detail pages, records with edit pages), and the validator walks every link to
  check.
- **Give boards that manage assets one familiar shape.** The asset types are the
  main menu. An asset type's page lists its assets in a sidenav, with a "New"
  floating action button on top. An asset opens its detail page with settings and
  delete, and further aspects go on tab pages. Sub-assets repeat this one level
  down. A full-width asset page needs a prominent back button in the top-left
  corner. board-template.md, "Boards that manage assets", has the details.
- **Use only names that exist.** Every table, column and widget property you write
  must exist in data-template.yml or the widget's schema. The platform ignores unknown
  keys silently, so an invented key renders as nothing rather than as an error.
- **Keep the schema line.** Start every template with
  `# yaml-language-server: $schema=https://ironflock.com/schemas/<name>/v1.yml`, so
  the developer's editor validates the file too. Older platform versions dropped
  comments from board-template.yml when the board was saved in the editor, so
  re-add the line there if it has gone missing.
- **Leave platform-only values to the board editor.** The numeric app and device keys
  that switch and SCADA actions target only exist in a running project. Leave them
  out and tell the user to pick them in the editor.
- **Don't touch what you weren't asked to change.** Existing boards can carry configs
  from older widget versions. Fix validator errors in widgets you add or edit. For
  errors in widgets you didn't touch, report them instead of rewriting them silently.
