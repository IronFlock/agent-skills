# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `npm start` — Vite dev server on port 8000, opens `/demo/`, runs `vite build --watch` in parallel. The demo stands in for Studio: it paints the tile, sets the `--re-*` custom properties, switches themes, and sends a new `inputData` object every second.
- `npm run build` — Type check (`tsc -p .`), then the Vite library build → `dist/widget-starter.js` (ES only).
- `npm run watch` — Rebuild on changes without the dev server. Studio's dev server serves this `dist/` when the repo sits in `../ironflock-widgets/` next to `studio/`.
- `npm run types` — Regenerate `src/definition-schema.d.ts` from `src/definition-schema.json` with `json2ts`. Run it after every schema edit; never edit the `.d.ts` by hand.
- `just lint` — what the CI gate checks besides the build: regenerating the committed generated files (`npm run types`) changes nothing. `just build` = `npm run build`.
- `just merge` / `just release-patch` (`release-minor`, `release-major`) — pull requests into `main` from a feature branch with everything committed: a no-release one, or a release one whose merge publishes to npm in CI (`.github/workflows/build-publish.yml`), then the release GitHub App tags the bare version and creates the GitHub release. Never `npm publish`, tag or edit the version by hand.

Node `>=24.9.0`, npm `>=10.0.2` (per `engines`).

## Architecture

A single-file LitElement web component published as `@ironflock/widget-starter`, rendered on IronFlock boards by Studio.

**Entry point:** `src/widget-starter.ts` defines `<widget-starter-versionplaceholder>`. `@rollup/plugin-replace` (in `vite.config.ts`) rewrites `versionplaceholder` to the `package.json` version at build time, so each published version registers its own tag (`widget-starter-1.0.0`) and several versions can coexist on one page. Studio renders `<widget-starter-<pinned version>>`; a bundle that registers any other name leaves the tile spinning with no error.

**Platform integration:** the host sets these properties:
- `inputData: StarterConfiguration` — the tile's config, shaped by `src/definition-schema.json`, with every data binding already replaced by its rows (`tableRef`, oldest first) or value (`valueRef`). A new object arrives on every data update. It may be `{}`, partial, or written for an older version, and it belongs to the host: never write to it.
- `theme: { theme_name, theme_object }` — an ECharts theme; `theme_object` can be missing. Text colours are `var(--re-text-color, <theme colour>)` chains built in `render()`, so the host's custom property wins and a board style edit repaints without the widget being told. The widget paints no background: Studio's `widget-item` paints `--re-tile-background-color` on the tile.

**Data flow:** `willUpdate()` turns `inputData` into `readouts` with the pure `toReadouts()` when it changes: one readout per series, or one per distinct `pivot` value, each showing the value of its newest row. `render()` lays the readouts out in a grid; sizes come from container query units on `:host` (`container-type: size`), so no ResizeObserver is needed.

TODO: describe this widget's own data flow and design decisions here as they are made.

**Build:** Vite library build (`build.lib`), one ES module with a sourcemap. `lit` is external: Studio's import map provides it, so every widget shares one copy. Externalize only what that import map provides; bundle everything else.

## Schema editing workflow

When changing the widget configuration: edit `src/definition-schema.json`, run `npm run types`, then update the code. Descriptions in the JSON schema are user/agent-facing: Studio shows them as help texts and the IronFlock AI reads them to configure the widget. Keep `title`, `description`, `type` and `order` on every property. Never rename, retype or remove a property that a released version had: boards keep configs written for older versions.

## `aiSelection` in `src/definition-schema.json`

The schema root carries an `aiSelection` block next to `title` and `description`. It is **not** JSON Schema and describes no config field — it exists so the IronFlock AI's Widget Builder can pick the right widget for a given shape of data, using knowledge only the widget author has:

```jsonc
"aiSelection": {
  "dataShape": "…what columns this widget consumes and what each one means…",
  "useWhen":   ["…a situation, naming the properties that express it…"],
  "notFor":    ["…a situation this widget is wrong for, naming the widget to use instead…"]
}
```

It is inert everywhere else, and must stay that way: `json2ts` ignores it, the dashboard config editor renders only `schema.properties`, and the AI service's `validate_widget` validates *configs* against the schema, skipping unknown Draft-7 keywords.

When maintaining it:

- `notFor` is the high-value half and the part plain descriptions always omit. Every entry must name the widget that *should* be used, or it rejects without routing.
- Write for an LLM with no other documentation: describe the visible result and the user's intent, not the implementation.
- Prefer entries that discriminate against a *neighbouring* widget. Generic rejections are cheap; the ones that pay are those an author could plausibly get wrong.
- The `notFor` lists are a set across all `widget-*` repos and are meant to be reciprocal — if this widget routes to another for some case, that widget should usually route back for the converse. Changing one side is a cue to check the other.
- Update it whenever a property changes what this widget can *do*, not just how it looks.
