---
name: ironflock-widgets
description: Build, change, fix and release IronFlock board widgets, the Lit web components published as @ironflock/widget-* npm packages (repos IronFlock/widget-*, checked out in an ironflock-widgets folder) that draw the tiles of IronFlock boards in Studio. Covers the component code, the config schema (src/definition-schema.json with its aiSelection block), src/default-data.json, theming, sizing, the events a widget sends to Studio, the build, the demo, the release, and creating a new widget type from a template. Use this whenever you work in a widget-* repository, add or change a widget setting, fix a widget that renders wrong or blank, or create a new kind of widget, even if the user only says "the gauge" or "the linechart". To place and configure existing widgets on an app's board (board-template.yml), use ironflock-templates instead.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# IronFlock widgets

A widget is an npm package, `@ironflock/widget-<name>`, that registers one Lit web
component. Studio, IronFlock's board UI, loads the exact version a board pins from
a CDN, creates `<widget-<name>-<version>>` in a tile, and feeds it the tile's
config. Data comes in through properties; the widget acts only by dispatching
events, and Studio does all fetching, writing and navigating.

| Studio gives the widget | The widget gives Studio |
|---|---|
| `inputData`: the tile's config, with data bindings replaced by rows or values; a new object on every update | `nav-submit` `{ path }`: open a board page |
| `theme`: `{ theme_name, theme_object }`, an ECharts theme that may be missing | `param-submit` `{ params }`: set URL parameters for filters |
| `route` and `timeRange`, for widgets that need them | `action-submit`: call a device function |
| CSS custom properties `--re-text-color`, `--re-tile-background-color`, … | `data-submit`: write a row to a table |
| a painted tile; the element is sized 100% of it | |

[references/host-contract.md](references/host-contract.md) has the details.

## Workflow

1. **Read before changing.** In the widget's repo, read `CLAUDE.md` (its own
   decisions and gotchas), `src/definition-schema.json` and the component source.
   Then run the checker once, so you can tell what was already there from what
   you introduce:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/check_widget.py <repo>
   ```

2. **Schema first.** A new or changed setting starts in
   `src/definition-schema.json`; then run `npm run types` and change the code.
   Read [references/config-schema.md](references/config-schema.md) before you
   touch the schema, because its keywords don't all mean what JSON Schema says.
3. **Code** by [references/component.md](references/component.md). Before solving
   a sub-problem (a chart, a menu, a device action), look at the widget that
   already solves it ([references/widget-index.md](references/widget-index.md)).
4. **Keep the rest in step**: `src/default-data.json` stays a valid, neutral
   example; `aiSelection` changes when the widget can do something new; `layout`
   when its natural height or width changes; `CLAUDE.md`
   and `README.md` describe what you changed.
5. **Verify**:
   - `npm run build` must pass.
   - `check_widget.py <repo> --since HEAD` shows only the findings your change
     introduced. Fix every ERROR; fix or justify every WARN. Add `--typecheck` in
     repos whose build doesn't type-check.
   - `npm start` and look at the demo with the default config, `{}`, a light and a
     dark theme, and a small and a large tile, with no console errors. If you can
     drive a browser, do; otherwise ask the user to look.
   - For integration, Studio's dev server picks up the sibling checkout
     ([references/repo-and-release.md](references/repo-and-release.md#testing-in-studio)).
6. **Stop before releasing.** `just release-patch` publishes to npm, and a published
   version can never be changed. Release only when the user asks, and then tell
   them which platform steps the release needs
   ([references/repo-and-release.md](references/repo-and-release.md#after-a-release)).

**A new widget** starts from the template:
`python3 ${CLAUDE_SKILL_DIR}/scripts/new_widget.py <name> --dest <folder>`.
Read [references/new-widget.md](references/new-widget.md) first: check with the
user that it should be a new widget at all, and plan the platform registration it
needs.

## Rules

Each of these comes from how Studio hosts widgets or from a bug that shipped.

**Identity and compatibility**

1. **One package, one versioned element.** Register
   `@customElement('widget-<name>-versionplaceholder')`; the build puts the version
   in. Never write a version number into code or the demo. Any other element the
   bundle defines needs the same suffix, because two versions of a widget can share
   a page and a second `define` of a name throws.
2. **Never break an old config.** Boards keep their pinned version and their config
   for years, and a user can move a tile to a new version with its old config. Add
   settings with defaults that keep the old look; never rename, retype or remove
   one. A renamed key's stored values become invisible to the editor and the AI,
   and inside a settings object Studio strips them before the widget sees them.

**The config**

3. **The schema is the contract.** Studio's editor builds the settings form from
   it, Studio strips undeclared keys inside settings objects, and the AI configures
   widgets from its descriptions and rejects undeclared keys. Give every property
   `title`, `description`, `type` and `order`. Never edit the generated `.d.ts`.
4. **Treat `inputData` as read-only, untrusted and partial.** It belongs to the host
   and shares rows with other tiles, can be `{}`, and any field can be missing,
   `null`, `''` or of the wrong type. Derive what you draw from it with a pure
   function, apply defaults in code (the schema's `default` never reaches the
   widget), and check a setting's `condition` yourself (Studio doesn't strip hidden
   fields).
5. **Never throw.** There is no error boundary around a widget: an exception in a
   lifecycle method blanks the tile or breaks the board.

**Rendering**

6. **Fill the tile, at any size.** `:host { display: block }`, then size everything
   by the tile: container query units (`container-type: size` on `:host`), or a
   `ResizeObserver` for chart and map libraries. Tiles resize constantly, can be
   20 px, and hidden pages keep widgets mounted at 0 × 0.
7. **Leave the tile to the host; take colours from `var()` chains.** Studio paints
   the tile, translucent by default; painting `--re-tile-background-color` again
   doubles it. Write colours as `var(--re-text-color, <theme colour>)` so board
   style edits repaint without the widget; never cache `getComputedStyle()`.
   Only canvas drawing and opaque menu surfaces resolve a colour, at the point of
   use.
8. **Act only through the four events.** No `window.location`, history, storage,
   `fetch` of platform data or connections. Read `route` and `timeRange` from
   properties. The editor's preview and the AI chat run real writes and device
   actions too.
9. **Survive detach and re-attach.** Studio moves tiles by disconnecting and
   reconnecting them in one task. Release observers, timers, listeners and chart
   instances on disconnect (instances after a `setTimeout`, if still detached) and
   restore them on reconnect.
10. **Follow the data conventions.** Bound rows arrive oldest first. Timestamps are
    epoch-millisecond numbers (`Date.parse` turns them into `NaN`); accept ISO
    strings too. Widgets don't aggregate; the data layer does. Format numbers and
    dates for the viewer's locale.

**Build and release**

11. **Take shared libraries from Studio's import map.** `@material/web`, `@vaadin/*`,
    flatpickr, echarts and zrender must be external (they register elements or need
    one shared instance); lit, tinycolor2 and tslib may be. Bundle everything else
    into the one ES module `main` points at: any other bare import fails on cloud.
12. **ECharts**: register every component with `echarts.use`, build each option from
    `structuredClone(template)` (never from `getOption()`), keep the canvas
    background transparent, and dispose of instances.
13. **Release only through `just release-patch`, and only when asked.** It opens
    a release pull request; its merge publishes in CI. Never `npm publish` by
    hand, tag by hand or edit the version.

## Scripts

| Command | Does |
|---|---|
| `python3 ${CLAUDE_SKILL_DIR}/scripts/check_widget.py <repo>` | Checks a widget repo against these standards. `--since HEAD` shows only new findings; `--typecheck` also runs `tsc` on `src/`. |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/new_widget.py <name> --dest <folder>` | Scaffolds a new widget repo from the template. |

Both need only Python 3.9+. The checker's type checks need the repo's
`node_modules`. The template itself is in `${CLAUDE_SKILL_DIR}/assets/widget-template/`.

## References

| File | Read it when |
|---|---|
| [references/host-contract.md](references/host-contract.md) | you need to know exactly what Studio passes, renders, listens for, or how versions reach boards |
| [references/component.md](references/component.md) | writing or changing component code |
| [references/config-schema.md](references/config-schema.md) | changing `definition-schema.json`, `default-data.json`, `aiSelection` or `layout` |
| [references/repo-and-release.md](references/repo-and-release.md) | build config, dependencies, the demo, testing in Studio, releasing |
| [references/new-widget.md](references/new-widget.md) | creating a new widget |
| [references/widget-index.md](references/widget-index.md) | looking for an existing widget that solves a similar problem, or for patterns not to copy |

In an existing widget, fix what your change touches. Report older problems you
notice instead of rewriting code you weren't asked to change.

## IronFlock documentation

This skill covers the widget code. How users configure widgets on a board is
covered in the IronFlock docs: the widget reference, data binding, aggregation,
filters, forms, actions, styling and embedding, under
<https://ironflock.com/en/docs/iot-dashboards/>. Look a page up when a change
affects what users see in the board editor or the docs describe, or when you need
to know how a feature behaves for users. Don't guess from memory. Fetch
<https://ironflock.com/llms.txt> for the list of pages, then the page's Markdown:
its URL without the trailing slash plus `.md`. Where the docs and this skill's
references disagree on what Studio passes to a widget, host-contract.md is
authoritative. If a change makes a docs page wrong, tell the user which page.
