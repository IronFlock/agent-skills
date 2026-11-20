# The existing widgets

Read the widget that already solves your sub-problem before writing your own. Each
repo's `CLAUDE.md` records its decisions and gotchas.

## The widgets

| Widget | Shows | Talks to Studio | From Studio's import map (bundled) |
|---|---|---|---|
| widget-linechart | line, bar and scatter charts over time or categories | reads `timeRange` | echarts, tinycolor2 |
| widget-value | large numbers with label and unit | — | — |
| widget-gauge | gauges against a min/max with colour sections | — | echarts |
| widget-signal | status lamps coloured by value | — | lit |
| widget-doughnut | doughnut and pie charts | — | echarts |
| widget-table | rows and columns, with status colours, links and images | — | lit, @vaadin/grid |
| widget-heatmap | intensity over two categorical axes or a calendar | — | echarts |
| widget-statehistory | state timelines (which state, how long) | — | echarts (luxon, tinycolor2) |
| widget-mapbox | positions, tracks and areas on a map | host-set `accessToken` | — (mapbox-gl) |
| widget-scada | one industrial symbol (tank, pump, valve…) bound to data | `action-submit`, `widget-defaults`, host-set `baseUrl` | — |
| widget-label | one line of text | — | — |
| widget-textbox | a title and a text block (retired in the platform) | — | — |
| widget-markdown | markdown with `{{variables}}` | — | — (marked, highlight.js) |
| widget-image | images, one or several, filtered by time | reads `timeRange` | — |
| widget-overlay | an image with live values placed on it | — | — |
| widget-embed | a web page in an iframe | Studio rewrites tunnel URLs | lit |
| widget-form | a data-entry dialog that writes table rows, with file uploads | `data-submit`, `file-data-submit`, `nav-submit`, reads `route` | @material/web, lit-flatpickr |
| widget-switch | toggles that call device functions, or set URL parameters | `action-submit`, `param-submit`, reads `route` | lit, @material/web |
| widget-filter-dropdown | a dropdown that sets a URL parameter | `param-submit`, reads `route` | @material/web |
| widget-filter-calendar | a date or range picker that sets URL parameters | `param-submit`, reads `route` | @material/web, flatpickr, lit-flatpickr |
| widget-navbar | a top menu with the current page highlighted | `nav-submit`, reads `route` | lit, @material/web |
| widget-sidenav | a side menu with the current page highlighted | `nav-submit`, reads `route` | lit, @material/web |
| widget-navbutton | one navigation button | `nav-submit`, reads `route` | lit, @material/web |
| widget-toast | notifications popping up for new rows | — (Studio floats its tile) | — |

Widgets that don't take `lit` from the import map bundle their own copy. Both
work; externalizing it keeps the bundle small.

## Where to look

| You need | Look at |
|---|---|
| An ECharts chart: template clone, signatures, dispose on detach | widget-heatmap (smallest), widget-linechart (most complete), widget-gauge (fast data-only path) |
| Canvas text in the board's text colour | `resolvedTextColor()` in any ECharts widget |
| Text that scales to fill the tile | widget-value (measures and scales), widget-signal and the starter template (CSS `cq` units) |
| A pivot that splits data into several charts or readouts | widget-doughnut, widget-gauge, widget-linechart (`#split#` in chart names) |
| Reading and writing URL parameters | widget-filter-dropdown, widget-switch (view switch) |
| Navigation and current-page highlighting | widget-navbutton (smallest), widget-navbar, widget-sidenav |
| `*` and `{{variable}}` substitution in routes | `resolveRoute()` in widget-navbutton |
| Calling a device function with an optimistic state | widget-switch |
| Writing rows to a table | widget-form |
| An opaque menu or dialog over a translucent tile | `surfaceColor()` in widget-filter-dropdown and widget-form |
| Material Web components styled by tokens | widget-navbutton, widget-switch |
| A data grid | widget-table (vaadin-grid) |
| A map, a token from the host, retry on tile errors | widget-mapbox |
| A generated schema and a catalog for the AI | widget-scada (`scripts/`, `schema-curation.json`) |
| Timers that must die with the element | widget-toast |
| Hiding a value that goes stale while no new data arrives | `staleAt()` and `scheduleStaleCheck()` in widget-gauge and widget-value |
| Normalising malformed configs | widget-doughnut (`sections`), widget-gauge (section limits) |

## Patterns not to copy

Older code in the fleet still contains these (October 2026). They are known
defects or leftovers, not conventions:

- **Painting `--re-tile-background-color`**: widget-scada.
- **`cq` units without `container-type`**: widget-filter-dropdown, widget-navbutton,
  widget-switch (they resolve against the viewport).
- **Observers not re-attached after a DOM move**: widget-signal, widget-embed,
  widget-image, widget-scada.
- **Animation loops not stopped on disconnect**: widget-scada's runtime.
- **An object passed where a colour is expected**: widget-statehistory's
  `borderColor` from `timeAxis.splitLine.lineStyle`.
- **A class name copied from another widget**: widget-embed's `WidgetValue`.
- **Repo leftovers**: `types` in `package.json` pointing at a file the Vite build
  never emits, `link`/`unlink` scripts for `../RESWARM/frontend`, Rollup configs in
  repos that build with Vite, ESLint/husky devDependencies without any config,
  READMEs with hard-coded versions and unscoped package names.
- **Dead schema keywords**: `color: true`, `min`/`max`, property-level `required`,
  `enumLabels` objects ([config-schema.md](config-schema.md#other-keywords-and-dead-ones)).

widget-value, widget-gauge and widget-overlay show the fixed forms of others:
parsing a bound timestamp with `toDate()` and re-checking its age with a timer
(`scheduleStaleCheck()`), reading settings into locals instead of writing defaults
into `inputData`, and a versioned helper element
(`widget-overlay-progress-versionplaceholder`).
