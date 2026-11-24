# IronFlock Dev

Build on IronFlock with Claude: apps that run on your edge devices, the
boards that show their data, and the board widgets themselves.

IronFlock is a platform for fleets of edge devices. An IronFlock app is a
container that runs on every device, keeps its state in the app's tables and
brings a board, the app's user interface, bound live to those tables. This
plugin teaches Claude how such an app is meant to be built, and gives it a
starter app, the schemas and a validator, so that what it writes installs
and renders.

It is made for Claude Code, where Claude works in a checkout of your app or
widget repository.

## What you can ask

- "Build an IronFlock app that reads our filling machines and shows fill
  level and faults per machine."
- "Add a page to this app's board with the temperature of each device over
  the last day."
- "Add a table for maintenance orders, with a list and a form on the board."
- "Validate this app's `.ironflock` folder."
- "Let users set the sampling interval as an app parameter."
- "Add a unit setting to the gauge widget."
- "Create a new widget that shows a progress bar."

## Skills

`ironflock-dev-run` handles “build the app”, “show the app logs” and “is it
running?” in the hosted IronFlock IDE. It uses IronFlock MCP to build the
current working copy on the development device and inspect its DEV run.

`ironflock-templates` is for apps:

- an interview before a new app or a refactor: what the app is for, who uses
  it, and which entities it deals with. The tables, lists, forms and pages
  are built from that entity model;
- the architecture: where each kind of data goes, how a device follows what
  users set on the board, and how a web UI that a device serves is embedded
  in the board;
- a starter app and `new_app.py`, which scaffolds a new app from it, with a
  `design/` folder that records the app's purpose, entities and board;
- a design step for the board: who looks at it and where, one meaning per
  colour, eight style presets;
- the rules for the files in the app's `.ironflock/` folder:
  `board-template.yml` (widgets, data bindings, pages, layout),
  `data-template.yml` (tables and transforms), `env-template.yml` (app
  parameters), `port-template.yml` (remote-access ports), `ai-template.yml`
  (the app's AI agents) and the app's skills;
- a catalog of the board widgets, a tool that reads any widget's published
  configuration schema, and a validator. The validator catches mistakes the
  platform would report only at install time, or not at all, such as a widget
  bound to a column that does not exist, or a page that no click can reach.

`ironflock-widgets` is for the widgets, the `@ironflock/widget-*` npm
packages whose Lit web components draw a board's tiles:

- what Studio gives a widget and expects from it: properties, events,
  sizing, theming, versions, shared libraries;
- standards for the component code, the configuration schema, the build and
  the release;
- a starter template and `new_widget.py`, which scaffolds a widget
  repository from it;
- `check_widget.py`, which checks a widget repository against those
  standards.

The skills start on their own when you work on an IronFlock app or a widget.
You can also call them as `/ironflock-dev:ironflock-templates` and
`/ironflock-dev:ironflock-widgets`.

## Set up

Add the plugin from Claude's plugin directory, or in Claude Code from
IronFlock's marketplace:

```text
/plugin marketplace add IronFlock/agent-skills
/plugin install ironflock-dev@ironflock
```

`ironflock-dev` needs the plugin `ironflock`, which connects Claude to your
IronFlock instance. From IronFlock's marketplace, Claude Code installs it
together with this one. If you add `ironflock-dev` from the directory, add
`ironflock` there as well.

Editing and validating templates works offline with locally cached widget schemas.
Sign in when Claude needs to look at your instance, which is what
`ironflock` is for.

## Requirements

- Python 3.9 or later.
- [`uv`](https://docs.astral.sh/uv/) is recommended. The validator needs
  PyYAML and jsonschema and gets them through `uv run` by itself. Without uv,
  run `python3 -m pip install pyyaml jsonschema`.
- Network access to `registry.npmjs.org` and `cdn.jsdelivr.net` for the
  widgets' schemas. `validate.py --offline` skips the checks that need them.
- For widget work: Node.js 24 and npm, as the widget repositories require.

## Data

What the plugin sends, runs and fetches:

- **Development builds and logs.** The skill uses the hosted workspace’s IronFlock connection. The platform sends the working copy to the selected development device and returns build output and requested runtime logs.
- **Scripts.** The skills have Claude run Python scripts from the plugin's
  folder: `validate.py` (checks an app's `.ironflock` folder), `widget.py`
  (prints a widget's configuration schema), `new_app.py` and `new_widget.py`
  (copy a starter into a new folder and never overwrite an existing one) and
  `check_widget.py` (checks a widget repository). The skills allow Claude to
  run these scripts with `python3` or `uv run` without asking each time
  (`allowed-tools` in their front matter). Nothing else is allowed in
  advance.
- **What the scripts fetch.** `widget.py` and the validator read the public
  widget packages (`@ironflock/widget-*`, older releases
  `@record-evolution/widget-*`): the latest version from
  `registry.npmjs.org`, and the schema files from `cdn.jsdelivr.net`, or
  from `unpkg.com` when that fails. They keep them in
  `~/.cache/ironflock-templates`. If Python cannot open the connection, the
  script tries `curl`. These requests carry a package name and a version,
  nothing of yours.
- **What the scripts install.** When PyYAML or jsonschema is missing and uv
  is installed, `validate.py` runs itself again through `uv run`, which
  downloads these two packages from PyPI into uv's cache.
- **What `check_widget.py` runs.** With `--since` it reads an earlier
  revision of the widget repository through `git archive`, into a temporary
  folder. When that repository's `node_modules` are installed, it runs
  `json2ts` from them to compare the generated types, and with `--typecheck`
  also the TypeScript compiler. It also reads the import map of a Studio
  checkout next to the widget repositories, where IronFlock's own developers
  have one.
- **The starters.** `new_app.py` writes a Python program, its Dockerfile, a
  `requirements.txt` that pins the IronFlock SDK and aiohttp, the
  `.ironflock` templates and design documents. `new_widget.py` writes a
  widget repository with a `package.json`, a build configuration and GitHub
  Actions workflows for checks and for publishing to npm. None of this runs
  until you build it, or push it to a repository of your own.

## Help

- [Build with Claude Code](https://ironflock.com/docs/app-development/claude-code/)
  and [app development](https://ironflock.com/docs/app-development/) in the
  IronFlock documentation
- [Questions and problems](https://github.com/IronFlock/agent-skills/issues)
- [What each version changed](https://github.com/IronFlock/agent-skills/blob/main/CHANGELOG.md)

## License

MIT, see
[LICENSE](https://github.com/IronFlock/agent-skills/blob/main/LICENSE).
