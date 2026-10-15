# Writing the component

The standards for a widget's Lit code. Each rule comes from how Studio hosts
widgets ([host-contract.md](host-contract.md)) or from a bug that shipped in one
of the existing widgets. The starter template (`assets/widget-template/src/widget-starter.ts`)
follows all of them; read it next to this file.

## Contents

1. [The element](#the-element)
2. [Lifecycle and derived state](#lifecycle-and-derived-state)
3. [Reading the config](#reading-the-config)
4. [Data conventions](#data-conventions)
5. [Size](#size)
6. [Colours and theme](#colours-and-theme)
7. [Events](#events)
8. [Attach, detach and cleanup](#attach-detach-and-cleanup)
9. [Shared libraries](#shared-libraries)
10. [ECharts](#echarts)
11. [Menus, dialogs and tooltips](#menus-dialogs-and-tooltips)
12. [Security](#security)
13. [Text, locale and accessibility](#text-locale-and-accessibility)
14. [Performance](#performance)

## The element

```ts
@customElement('widget-gauge-versionplaceholder')
export class WidgetGauge extends LitElement {
    @property({ type: Object }) inputData?: GaugeChartConfiguration
    @property({ type: Object }) theme?: Theme

    version: string = 'versionplaceholder'
```

- **One package registers one versioned element.** The build replaces
  `versionplaceholder` with the package version, so every release registers its
  own tag and boards pinned to different versions can share a page. Never write a
  version number into code, tags or the demo.
- **Every other custom element the bundle defines needs the suffix too**:
  `@customElement('widget-overlay-progress-versionplaceholder')`, never
  `@customElement('linear-progress')`. A second `customElements.define()` of the
  same name throws, and two versions of a widget on one page do exactly that.
  Elements of shared libraries (`md-*`, `vaadin-*`) are the exception, because
  the host's import map makes sure they are defined once.
- Prefer the `@customElement` decorator over `customElements.define()`, and name
  the class after the widget (`WidgetGauge`, not a copied `WidgetValue`).
- Type `inputData` with the root interface generated from the schema
  (`src/definition-schema.d.ts`). Declare no inputs besides `inputData` and
  `theme` unless the host sets them (`route`, `timeRange`; see the host contract).
- `tsconfig.json` must keep `experimentalDecorators: true` and
  `useDefineForClassFields: false`. esbuild reads both; with standard class-field
  semantics a decorated property shadows Lit's reactive accessor and stops
  triggering updates.

## Lifecycle and derived state

- **Derive what you draw from `inputData` in `willUpdate()`** (or in an
  overridden `update()` before `super.update()`, as most existing widgets do),
  and only when it changed:

  ```ts
  protected willUpdate(changed: PropertyValues<this>): void {
      if (changed.has('inputData')) this.readouts = toReadouts(this.inputData)
  }
  ```

  State set there does not trigger another update. Never set reactive state in
  `render()` or `updated()` without a guard; it schedules another update, and in
  `updated()` it can loop.
- **Keep the transform a pure function** of the config: it takes `inputData` and
  returns new objects. That makes "never mutate inputData" automatic, and the
  function easy to test.
- **DOM measurement and imperative libraries go in `firstUpdated()` / `updated()`**,
  after the render they depend on.
- `inputData` changes on every realtime row. Work that only depends on settings
  (layout, chart structure) should run when the settings changed, not on every
  row: compare a signature of the settings with the previous one
  (`JSON.stringify` of the relevant fields is what the fleet uses).
- **Never throw.** There is no error boundary around a widget. Treat every value
  as possibly missing, and keep code that can throw (parsing user patterns, third
  party calls) inside `try`/`catch` with a sensible fallback.

## Reading the config

`inputData` belongs to the host, can be `{}`, and can come from any older version
of the widget or from a hand-written board template.

- **Never write to it**, not even a default: no `ds.advanced.averageLatest = 1`, no
  `this.inputData.dataseries.sort(...)`, no `??=` on its fields. Rows are shared
  with other tiles. Copy before sorting (`[...rows].sort()`), and read defaults
  into locals: `const precision = ds.precision ?? 0`.
- **Check types, not just presence.** Use `Array.isArray(x) ? x : []` for lists,
  skip `null` slots in them (a stray `-` in a board template makes one), and
  convert numbers with a helper that rejects `NaN`:

  ```ts
  const toNumber = (value: unknown): number | undefined => {
      if (value === null || value === undefined || value === '') return undefined
      const number = typeof value === 'number' ? value : Number(value)
      return Number.isFinite(number) ? number : undefined
  }
  ```

- **`''` means unset** for colours and most texts: the editor stores an unset
  colour as `''`, and a cleared text field as `''`. Use `||` for those fallbacks,
  `??` for numbers and booleans.
- **Apply defaults in code.** The schema's `default` is only a hint for the editor
  form; the widget receives no value. Every optional setting needs a fallback in
  the code, and that fallback must match what the schema's description promises.
- **Respect conditions yourself.** Studio does not strip a field whose `condition`
  is not met, so code that reads `value` must also check the switch that enables
  it (`if (!ds.multiChart) ...`).
- **Keep accepting old shapes.** If a release changes a setting's shape, keep
  reading the old shape too, because boards keep their configs. widget-doughnut
  folds a flat `sections` list into the expected list of rows rather than
  crashing on it.
- **Clamp what feeds an API that throws**: `toFixed()` throws outside 0–100, a
  negative or fractional precision from a config must not reach it.

## Data conventions

- **Bound rows arrive oldest first.** The newest row is the last one. Use
  `rows.at(-1)` or `rows.slice(-n)`, never `rows[0]`.
- **Timestamps of bound columns are epoch milliseconds** (numbers). Static configs
  and older paths can hold ISO strings. `Date.parse(1760000000000)` is `NaN`, so
  never `Date.parse` a timestamp; accept both forms:

  ```ts
  const toDate = (value: unknown): Date | undefined => {
      if (value === null || value === undefined || value === '') return undefined
      const ms = /^\s*-?\d+(\.\d+)?\s*$/.test(String(value)) ? Number(value) : Date.parse(String(value))
      return Number.isFinite(ms) ? new Date(ms) : undefined
  }
  ```

- **Pivot**: a `pivot` field in a row splits a series into one series (chart,
  readout) per distinct value. The fleet's conventions: group rows by
  `String(pivot)`, sort the groups naturally
  (`a.localeCompare(b, undefined, { numeric: true })`), label each
  `<pivot> - <label>` (or just one of them when the other is empty), and key
  charts by series index plus pivot, never by the label (two series can share
  one).
- **No aggregation in the widget.** Counting, summing and averaging over time
  happen in the data layer (a binding's `series` aggregation or a transform), so
  the same numbers appear wherever the data is shown. The only reductions widgets
  do are local display smoothing such as "average of the newest N rows". Say so
  in the schema and in `aiSelection`, or the AI picks the widget for a count it
  cannot make.
- **Staleness** ("hide values older than N seconds") compares the newest row's
  timestamp, parsed with `toDate`, with `Date.now()`. Studio sends `inputData` only
  when data arrives, so a check that runs only then never fires for a device that
  went silent: keep one timer for the moment the next value goes stale, clear it on
  disconnect and re-arm it on reconnect (`scheduleStaleCheck()` in widget-gauge).
- **JSON columns** arrive as objects; a binding can address a leaf of them. Treat
  their content as untyped.

## Size

- `:host { display: block; box-sizing: border-box; overflow: hidden; }`. Studio
  sizes the element 100% × 100% of the tile but sets no `display`.
- **Size everything by the tile, not the window.** Two good ways:
  - CSS container queries: `container-type: size` on `:host`, then `cqw`, `cqh`
    and `cqmin` units and `@container` rules inside. No JavaScript, no observer.
    Units like `2cqh` without a container resolve against the viewport, so
    always declare the container.
  - A `ResizeObserver`, when a library needs pixel sizes (charts, maps, canvas).
- Tiles go from 20 px to full screen and resize constantly. Hidden pages keep their
  widgets mounted at **0 × 0**: skip layout work when a size is 0 rather than
  dividing by it.
- A `ResizeObserver` callback that changes the size of what it observes loops
  ("ResizeObserver loop completed with undelivered notifications"). Defer such
  work with `requestAnimationFrame`; a microtask is not enough.
- For text that must fill the tile (big numbers), either use `cq` units with
  `clamp()`, or measure once and scale (widget-value fits a grid of readouts by
  computing a scale factor; widget-gauge does the same for its gauges).

## Colours and theme

- **The host paints the tile.** Never paint `--re-tile-background-color` (or the
  theme's `backgroundColor`) on the widget: the tile is translucent by default,
  and painting it twice doubles the colour. Paint backgrounds only where the
  user configured one.
- **Use `var()` chains, never snapshots.** The host's custom property wins, the
  theme's colour is the fallback, and the browser resolves it on every paint:

  ```ts
  const title = this.theme?.theme_object?.title
  const textColor = `var(--re-text-color, ${title?.textStyle?.color ?? 'inherit'})`
  ```

  Reading `getComputedStyle(this).getPropertyValue('--re-text-color')` once and
  caching it leaves the widget on the old colour after a board style edit, because
  that edit changes only the custom property.
- **Two exceptions read the computed value, at the point of use, never cached:**
  - Canvas drawing (ECharts and the like) cannot resolve `var()`. Resolve the
    colour each time the chart option is built (the `resolvedTextColor()` helper
    in widget-gauge, -linechart, -heatmap, -statehistory, -doughnut).
  - An opaque surface for a menu or dialog: composite
    `--re-tile-background-color` over `--re-background-color` over white
    (`surfaceColor()` / `opaqueSurface()` in widget-filter-dropdown). Parse colours
    through a canvas context's `fillStyle`, never by reading pixels (Firefox's
    fingerprinting protection randomises them), and never by stripping the alpha
    from the string.
- Don't branch on `theme_name`. Derive subtle colours from the text colour
  instead: `color-mix(in srgb, currentColor 35%, transparent)` for grid lines,
  scrollbars and empty states.
- Don't rely on custom properties Studio never sets (`--re-primary-color`,
  `--re-accent-color`, `--re-hover-color`, `--re-border-color`).
- json2ts types a `type: "color"` field as an empty interface, so read colours
  with a `typeof value === 'string'` check.

## Events

The widget never navigates, writes or calls anything itself. It dispatches one of
the four events Studio handles, and Studio does the work with the viewer's
permissions:

```ts
this.dispatchEvent(
    new CustomEvent('nav-submit', { detail: { path: '/machines/' }, bubbles: true, composed: true })
)
```

| To | Dispatch | Example |
|---|---|---|
| Open a board page | `nav-submit` `{ path }` | widget-navbutton |
| Set or clear URL parameters for filters | `param-submit` `{ params: { key: value \| undefined } }` | widget-filter-dropdown, widget-switch (view switch) |
| Call a device function | `action-submit` `{ actionApp, actionDevice, actionTopic, args }` | widget-switch, widget-scada |
| Write a row to a table | `data-submit` `[{ swarm_app_databackend_key, table_name, column_name, value }]` | widget-form |

- Read the current state back from the host, not from what you sent: filter
  widgets read their selection from `route`, a switch from its bound value.
- `action-submit` returns nothing. Show the requested state optimistically and
  fall back to the reported value after a timeout (widget-switch waits 10 s).
- The Widget Editor's preview and the AI chat also perform writes and device
  calls. There is no way to tell them apart from the board, so keep destructive
  actions behind an explicit click.
- No `window.location`, `history`, `localStorage`, `fetch` of platform data,
  WebSocket, WAMP or MQTT. Data comes through `inputData`, actions go through
  events.

## Attach, detach and cleanup

Studio moves tiles by moving their DOM nodes, which disconnects and reconnects the
element **within one task**. Pages are evicted, the AI chat disables widgets, and a
version switch replaces the element. So:

- Release everything in `disconnectedCallback()`: observers, timers, listeners on
  `window` or `document`, animation frames, chart and map instances.
- Re-create it in `connectedCallback()` when `this.hasUpdated` (after a move).
  `firstUpdated()` runs only once.
- Dispose expensive instances after the task, so a move keeps them:

  ```ts
  connectedCallback() {
      super.connectedCallback()
      if (this.hasUpdated && this.container) this.resizeObserver.observe(this.container)
      if (this.hasUpdated && (this.chartsStale || !this.charts.size)) this.rebuildCharts()
  }

  disconnectedCallback() {
      super.disconnectedCallback()
      this.resizeObserver.disconnect()
      // A DOM move disconnects and reconnects within one task: decide after it.
      setTimeout(() => {
          if (!this.isConnected) this.deleteCharts()
      })
  }
  ```

- Don't create instances while detached; mark them stale and rebuild on reconnect.
- Register a library's event handlers once per instance, when you create it, never
  per data update (closures pile up).

## Shared libraries

Studio's import map gives all widgets one copy of lit, `@material/web`, echarts,
zrender, vaadin, flatpickr, tinycolor2 and tslib
([host-contract.md](host-contract.md#loading) has the list).

- **Must be external** (in `rollupOptions.external`): libraries that register
  custom elements (`@material/web`, `@vaadin/*`, `lit-flatpickr`, `flatpickr`) and
  those whose classes are checked with `instanceof` across modules (`echarts`,
  `zrender`). Bundling them defines `md-*` elements twice or breaks the canvas
  renderer.
- **May be external**: `lit` (most new widgets externalize it), `tinycolor2`,
  `tslib`.
- **Everything else must be bundled.** A bare import of anything the map does not
  provide fails on cloud. Import echarts only through `echarts/core`,
  `echarts/charts`, `echarts/components`, `echarts/renderers` and
  `echarts/features`; bare `echarts` is for `import type` only.
- Declare externals as `peerDependencies` (and `devDependencies`, for the demo and
  the type checker), with ranges that include the import map's version.
- Material Web: `md-icon` relies on the page's "Material Symbols Outlined" font;
  the host loads it. Style Material components through their `--md-*` tokens, and
  derive the token colours from the configured or theme colours, not hard-coded
  accents.

## ECharts

The five chart widgets (linechart, heatmap, statehistory, gauge, doughnut) share a
pattern that removed a series of production bugs:

```ts
import * as echarts from 'echarts/core'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([GridComponent, TooltipComponent, LineChart, CanvasRenderer])
```

- **Register every component and chart type the option uses** with `echarts.use`.
  Importing it is not enough; an unregistered component is silently missing
  (that is how statehistory lost its toolbox).
- **Build every option from a clone of a plain template**:
  `const option = structuredClone(this.template)`, then fill in data and attach
  formatters (functions cannot be cloned, so keep them out of the template). Never
  feed `getOption()` back into `setOption()`: it returns every component as an
  array, the option nests one level deeper on each update, and a board left open
  dies with "Maximum call stack size exceeded" after an hour.
- **`notMerge: true` only when the structure changed** (series count, axis types,
  orientation), detected by a signature of the settings. Otherwise merge, which
  keeps zoom and animation state. `lazyUpdate: true` for data-only updates.
- **`backgroundColor: 'transparent'` in the option.** `echarts.registerTheme()` is
  global by name and carries the theme's background, which would paint an opaque
  slab over the tile.
- Text colours on the canvas come from `resolvedTextColor()` at build time (see
  [Colours and theme](#colours-and-theme)).
- Create one instance per chart with `echarts.init(div, this.theme?.theme_name)`,
  resize it from a `ResizeObserver`, and `dispose()` it after a real detach. A
  theme change needs new instances, because the theme is fixed at `init`.
- Reserve space for the title, legend and zoom slider (fixed rows; a single-row
  `legend: { type: 'scroll' }`), so they never overlap the plot.

## Menus, dialogs and tooltips

A tile clips its content and is its own stacking context. Anything that must
extend beyond the tile (a dropdown menu, a dialog, a tooltip) has to be in the top
layer: `md-dialog`, a `<dialog>` shown with `showModal()`, the popover API, or a
Material menu that uses it. Give it an opaque surface (see above), because the
tile colour behind it is usually translucent.

## Security

Board configs are written by users, and a board can be shared with people who did
not write it.

- Render config text as text (Lit bindings escape it). `unsafeHTML` is only for
  content the widget is about (widget-markdown) and should be sanitised.
- Bind styles with `styleMap`, which sets one property per key, rather than
  interpolating config strings into a `style` attribute.
- Links that open a new tab need `rel="noopener noreferrer"`.
- `<iframe>`s (widget-embed) should use `sandbox` unless the embedded app needs
  more.
- No `eval` or `new Function` on config content.
- Never put tokens or keys into the bundle. A widget that needs one gets it from
  the host (widget-mapbox's `accessToken`), which takes a change in Studio.

## Text, locale and accessibility

- There is no translation mechanism for widgets. Keep built-in UI text short and
  rare ("No Data"), and let the config carry everything users read.
- Format numbers and dates in the viewer's locale and time zone:
  `new Intl.NumberFormat(undefined, …)`, `new Intl.DateTimeFormat(undefined, …)`.
  Cache formatters at module level; constructing one per value is slow.
- Interactive parts must be real controls: `<button>` or Material components, not
  a `<div @click>`, so they work with a keyboard and a screen reader. Give
  icon-only controls an `aria-label`.
- Don't put essential information only into a hover tooltip; boards also run on
  touch screens and in screenshots.

## Performance

- A busy table delivers many rows per second, each as a new `inputData`. Keep
  the transform linear in the number of rows, avoid re-creating heavy objects
  (charts, maps, formatters), and diff settings before expensive updates.
- Patch imperative libraries with the new data only (ECharts `setOption` merge,
  Mapbox `source.setData`), and rebuild only when the structure changed.
- Use `repeat()` with stable, unique keys. Duplicate keys corrupt Lit's DOM
  bookkeeping.
- Don't log on hot paths. Leave no `console.log` in released code.
