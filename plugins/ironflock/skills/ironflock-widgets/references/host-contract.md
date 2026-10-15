# What Studio gives a widget, and what it expects

Studio is the IronFlock frontend that renders boards. It is the only host widgets
have: the board view, the board editor, the Widget Editor's preview, the style
dialog's demo tiles and the AI chat all render widgets through the same
`widget-item` element. This file describes that contract as the platform
implements it.

## Contents

1. [Loading](#loading)
2. [Properties](#properties)
3. [The tile and its size](#the-tile-and-its-size)
4. [Theming](#theming)
5. [Events](#events)
6. [Where a widget renders](#where-a-widget-renders)
7. [Versions](#versions)
8. [Things a widget must never assume](#things-a-widget-must-never-assume)

## Loading

- A board stores, for every tile, a `package_name` (`widget-gauge`) and a pinned
  `version`. Studio imports `https://cdn.jsdelivr.net/npm/@ironflock/<package_name>@<version>`
  (unpkg as the fallback). The CDN serves the file named by `main` in
  `package.json`, so `main` must be the built ES module, `dist/<package_name>.js`.
- Studio then renders `<${package_name}-${version}>` and waits until that tag is
  registered. A bundle that registers any other name leaves the tile spinning
  forever, without an error anywhere.
- The bundle must be **one self-contained ES module**. It is loaded from a CDN
  URL, so relative imports of chunks or assets (`./chunk.js`,
  `new URL('x.svg', import.meta.url)`) resolve against the wrong place. Inline
  assets as strings, or get a base URL from the host (widget-scada's `baseUrl`).
- **Bare imports resolve through Studio's import map**, which gives every widget
  the same instance of the shared libraries. It maps:

  | Specifier | Version |
  |---|---|
  | `lit`, `lit/…`, `lit-html`, `lit-element/…`, `@lit/reactive-element` | lit 3.3.3 |
  | `@material/web/…` | 2.4.1 |
  | `echarts/core`, `echarts/charts`, `echarts/components`, `echarts/renderers`, `echarts/features`, `zrender/…` | 6.1.0 (bare `echarts` is **not** mapped) |
  | `@vaadin/grid`, `@vaadin/text-field`, `@vaadin/checkbox` and their bases | 25.1.3 |
  | `flatpickr`, `lit-flatpickr` | 4.6.13, 0.4.1 |
  | `tslib`, `tinycolor2`, `@open-wc/dedupe-mixin` | 2.8.1, 1.6.0, 1.4.0 |

  The map is part of Studio's page. Any other bare specifier left in the bundle
  fails to resolve on cloud, and the tile never appears.
- Besides `main`, Studio fetches `src/definition-schema.json` and
  `src/default-data.json` of the pinned version (both are required, or the widget
  cannot be added or edited), and `thumbnail.webp`, then `thumbnail.png`, for the
  palette. So `files` in `package.json` must ship `dist`, `src` and the
  thumbnails.
- **Dev mode** (Studio's Vite dev server): bare `widget-*` imports are aliased to
  the sibling folders `../ironflock-widgets/widget-*`, which resolve to their
  built `dist/`. Studio dedupes lit, `@material/web` and vaadin, and points
  echarts at `widget-gauge/node_modules/echarts`. The pinned version is rendered
  as is, so the local build must register exactly the version the board pins.
- **Appliance builds** bundle each widget package at the version Studio's lockfile
  installs, and render that build whatever version a board pins.

## Properties

Studio sets these properties (never attributes) on the element before its first
update:

| Property | Content |
|---|---|
| `inputData` | The tile's config, shaped by `definition-schema.json`, with every data binding replaced by data. |
| `theme` | `{ theme_name, theme_object }`. |
| `route` | The current page path relative to the board root, including `?query`. |
| `timeRange` | `{ start?, end? }`: the URL parameters a calendar filter set, as strings of epoch milliseconds. |
| `baseUrl` | widget-scada only: where its symbol SVGs are. |
| `accessToken` | widget-mapbox only: the Mapbox token. |

These names are taken: don't use them for anything else. Studio also binds the
element's `class` and `style` attributes, so never overwrite them on `this`.

### inputData

- **A new object arrives on every data update**: when the tile mounts, when its
  config or the route changes, and on every row the device publishes. Realtime
  rows are not throttled. Studio never mutates an object it already handed over,
  and it shares rows with other tiles, so the widget must never mutate it
  either.
- **Bindings are already resolved.** A `tableRef` at an array position becomes
  an array of rows shaped by the binding's `format` (the schema's `items`),
  **oldest row first**. A `valueRef` becomes the newest value of its column, or
  `null`. A missing table gives `[]`.
- **Constants arrive as plain values.** The `$str:`, `$num:` and `$bool:`
  prefixes a board stores are parsed away. A number field the user cleared is
  left out of an object and is `null` in an array.
- **Timestamps arrive as epoch milliseconds** (numbers): `tsp` and every other
  timestamp column. A static config can hold ISO strings instead.
- **Secret columns arrive masked** as `'••••••••'`.
- **Studio removes keys the pinned version's schema does not declare, and `null`
  values, inside declared object settings** before the widget sees them.
  Undeclared top-level keys and keys directly in list items pass through. Either
  way, a setting that is not in the schema is invisible in the editor and rejected
  by the AI: don't rely on one.
- **Studio does not apply `default` values or evaluate `condition`s.** A key whose
  condition is not met still arrives, until someone opens the tile in the editor
  and saves.
- **It can be `{}`**: right after a drop, when the data layer is slow (Studio
  renders anyway after 15 s), and in the AI chat. Any field can be missing,
  `null`, `''` or of an unexpected type, because boards keep configs written for
  older versions and board templates are written by hand.
- When the data layer fails, or the viewer lacks access, Studio shows its own
  notice and does not render the widget at all.

### theme

- `theme_object` is an ECharts theme (keys such as `color`, `backgroundColor`,
  `title.textStyle.color`, `title.subtextStyle.color`). Studio ships 14: light,
  dark, chalk, essos, halloween, infographic, macarons, purple-passion, roma,
  shine, vintage, walden, westeros, wonderland.
- `theme_object` is **undefined** on boards without a theme (`---`, and every new
  board) and in the AI chat.
- `theme_object` is loaded asynchronously and **merged into the same object**, so
  its arrival does not change the `theme` property. Read it at the point of use
  (in `render()`), not only when `theme` changes.
- Only `theme_name` is stored with the board.

### route and timeRange

- `route` is `''` at the board root, has no leading slash guarantee, and is
  undefined outside boards (Widget Editor, style demo, AI chat). Hidden pages that
  stay mounted get their own route. Never read `window.location`.
- `timeRange` is only set when the config has bindings with query parameters.
  Parse its values with `Number()`.

## The tile and its size

- Studio's `widget-item` paints the tile: `background-color:
  var(--re-tile-background-color, #ffffff80)`, a 1 px border
  (`--re-tile-border-color`), a radius (`--re-tile-border-radius`, default 8px)
  and `color: var(--re-text-color, #333)`. It clips overflow.
- The widget element gets `width: 100%; height: 100%` and no `display`. A custom
  element is `display: inline` by default, so the widget's `:host` must set
  `display: block` (or flex or grid). There is no padding.
- Sizes are real layout sizes, not CSS transforms, and they change all the time:
  window resizes, zoom (0.25× to 3× in edit mode), style changes, layout edits.
  A new tile is about 200 × 150 px. Tiles can be as small as 20 × 20 px, and
  pages that were visited stay mounted with `display: none` (up to 6), so a
  widget keeps receiving data at **0 × 0**.
- Other places: the Widget Editor preview is a user-resizable box (minimum
  100 × 24), the style dialog's demo tiles are 292 × 250, the AI chat 600 × 350.
- Each tile is its own stacking context and clips its content. A menu, dialog or
  tooltip that has to extend beyond the tile must use the top layer (a `<dialog>`,
  the popover API, or a Material component that uses it).
- Layout positions can carry `fixedWidth`/`fixedHeight` (the tile keeps a pixel
  size) and `aspectRatio` (widget-scada: the tile keeps the symbol's shape, and
  its background, border and radius are made transparent).

## Theming

CSS custom properties are set on the board and, for a tile with its own colours
(`custom_style`), on that tile's `widget-item`. They inherit into the widget's
shadow tree:

| Property | Default | Notes |
|---|---|---|
| `--re-text-color` | `#334d5c` | Overrides the theme's text colour. |
| `--re-background-color` | `#fefefe` | The board background, behind the tiles. |
| `--re-tile-background-color` | `#ffffff80` | Translucent by default, transparent with the light theme. |
| `--re-tile-border-color` | `#fefefe` | |
| `--re-tile-border-radius` | `8px` | |

- When a user picks a theme, Studio overwrites the board colours from it: the
  background and tile background from `backgroundColor`, the text from
  `title.textStyle.color`, the tile border from
  `timeAxis.splitLine.lineStyle.color[0]`.
- A board style edit only changes these custom properties; the widget is not
  told. A per-tile style change additionally calls `requestUpdate('theme')` on
  the element. A widget that resolves colours through `var()` chains needs
  neither.
- Never set by Studio, so don't rely on them: `--re-primary-color`,
  `--re-accent-color`, `--re-hover-color`, `--re-border-color`.
- Fonts: the page loads Roboto and Material Symbols Outlined (used by
  `md-icon`). There is no font variable for widgets.

## Events

The only way a widget acts on the platform is by dispatching an event on itself.
Studio listens on the element, so bubbling is not required; navigation widgets
dispatch with `bubbles: true, composed: true` anyway.

| Event | `detail` | What Studio does |
|---|---|---|
| `nav-submit` | `{ path }` | Opens a board page. `/x` is relative to the board root, anything else to the current page's parent. A `?query` in the path is merged into the URL (`'undefined'`, `'null'` or `''` delete a key). An empty path opens `/`. |
| `param-submit` | `{ params: { [key]: string \| undefined } }` | Merges the parameters into the URL of the current page. `undefined` or `null` deletes a key. Widgets bound with `useFilter` filters re-query. |
| `action-submit` | `{ actionApp, actionDevice, actionTopic, args }` | Calls the device function `<swarm>.<actionDevice>.<app>.<stage>.<actionTopic>` with `[args]`. `actionApp` is the numeric app key and must match exactly. The result is discarded; failures show a toast. Without `actionApp` or `actionTopic` nothing happens. |
| `data-submit` | An array of `{ swarm_app_databackend_key, table_name, column_name, value }` | Groups the items into one row per table, adds `tsp` (now), turns `NaN` into `null` and publishes the row to the app's table. Items without a key or table are skipped. |
| `file-data-submit` | `{ items, waitUntil }`: `data-submit` items plus file items `{ swarm_app_databackend_key, table_name, column_name, file: File, namespace, contentType }` | Studio after 3.5.8 only. Claims the event by calling `waitUntil(promise)` during the dispatch. Uploads each file into the FleetFiles namespace of the item's app under a key of its own (`<YYYY-MM-DD>/<random>/<file name>`), puts the key in as the item's value, then writes the rows as for `data-submit`. If an upload fails, no row is written. The promise resolves once the rows are written and rejects with an `Error` whose message (localized) says why, which the widget shows. |
| `widget-defaults` | A config object | Widget Editor only: replaces the defaults the form fills in (widget-scada sends the selected symbol's defaults). Needs `bubbles: true, composed: true`. |

- `nav-submit` and `param-submit` only work on boards. In the Widget Editor and the
  AI chat nothing handles them.
- `action-submit`, `data-submit` and `file-data-submit` work everywhere,
  **including the Widget Editor's preview and the AI chat**: a click there switches
  a real device, writes a real row or stores a real file.
- Any other event name is ignored. That is what makes a new event safe to add: a
  widget that sends one must check that a host handled it (`file-data-submit`:
  nobody called `waitUntil`) and tell the user when none did, because an older
  Studio, or an appliance build that bundles one, silently drops it.
- Never put a `File`, `Blob` or other object into a `data-submit` value: Studio
  publishes it as JSON (`{}`), which lands in the column as garbage.

## Where a widget renders

| Context | Notes |
|---|---|
| Board, view mode | The normal case. |
| Board, edit mode | The element gets `style="pointer-events: none"`; Studio draws its own handles over the tile. The widget is not told that it is in edit mode. |
| Widget Editor preview | Live data from the unsaved config; every form change sends a new `inputData`. No `route`. |
| Style dialog demo | widget-gauge, widget-value and widget-linechart only: `default-data.json` is passed raw as `inputData`. |
| AI chat | The AI shows widgets it built; it can disable them, which removes the element. |
| Screenshots | A headless browser loads the board for reports, waits until the data is loaded plus about 5 s, fires a `resize`, and captures. The widget should reach its final look on its own, without hover or clicks. |

There is no "editing" property. A widget must look and behave the same in all of
them.

## Versions

- npm versions are immutable, and a board's pinned version is never rewritten. A
  widget dropped from the palette, or created or edited by the AI, gets the
  version the platform registered as current. Existing tiles move to a new version
  only when someone picks it in the Widget Editor's version list.
- So every released version keeps rendering for years, with configs written for
  it, and a new version receives configs written for every older one.
- For crash-class fixes Studio can set a minimum version per widget: on cloud,
  older pins render that version instead. Appliances always render
  the version they bundle.

## Things a widget must never assume

- That `inputData` is complete, current-schema, or safe to mutate.
- That `theme` or `theme_object` is defined, or that a new `theme_object` comes
  with a new `theme` object.
- That `route` is defined, or that `window.location` describes its page.
- That the tile background is opaque, or that the widget should paint it.
- That it is visible, large, or mounted only once. Studio reorders tiles by moving
  their DOM nodes, which disconnects and reconnects the element in one task.
- That it is the only version of itself on the page.
- That it can tell the editor or a preview from the live board.
- That `nav-submit` navigates everywhere, or that `action-submit` returns a
  result.
- That an exception stays inside the tile. There is no error boundary; a throw in
  a lifecycle method can blank the tile or break the board.
