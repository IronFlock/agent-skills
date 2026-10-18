# board-template.yml

The board is the app's dashboard. The platform installs it into every project the
app is installed in, and binds its widgets to that project's copy of the app's
tables. Developers usually build it in the board editor of the IronFlock studio,
which reads and writes this file. Writing it by hand is fine, and the editor picks
up your version.

Structure is defined by `schemas/board-template/v1.yml`. Each widget's own settings
are defined by its published definition schema (`scripts/widget.py <package>`).

## Contents

1. [Anatomy](#anatomy)
2. [Literal values](#literal-values)
3. [Binding data](#binding-data): valueRef, tableRef, queryParams, filters, aggregation
4. [What a binding can and cannot read](#what-a-binding-can-and-cannot-read)
5. [Pages and navigation](#pages-and-navigation): reachability, highlighting, link
   resolution, navigation patterns, filter widgets, uploading files with a form,
   embedding a web UI the app serves
6. [Layout](#layout)
7. [Style](#style)
8. [Markdown and HTML](#markdown-and-html): placeholders, HTML blocks
9. [SCADA pages](#scada-pages)
10. [Left to the board editor](#left-to-the-board-editor)
11. [Checklist](#checklist)

[example-board.yml](example-board.yml) is a complete, valid three-page board. It
has navigation, a data-driven machine menu, route filtering, aggregation and a
latest-per-machine table. Read it before writing your first board.

## Anatomy

```yaml
# yaml-language-server: $schema=https://ironflock.com/schemas/board-template/v1.yml
name: machine-monitor                # the app name
widgets:
    - layout_id: temperature         # this widget's id on the board
      package_name: widget-value     # widget type
      version: 1.1.33                # pin the version whose schema you used
      chartconfig:                   # the widget's settings
          title: $str:Temperature
          dataseries:
              - label: $str:Press 1
                unit: $str:°C
                value:
                    valueRef:
                        tablename: measurements
                        column: temperature
                        queryParams:
                            limit: 1
      custom_style:                  # optional: this tile's colours
          tile_background_color: '#e8f5e9'
layout:                              # the home page (route /)
    gridLayout:
        - {id: temperature, x: 0, y: 0, w: 96, h: 64}
style:
    columns: 96
    rows: 64
```

- **`name`**: write the app name. The editor overwrites it with the app name on
  every save anyway. It may only contain letters, digits, spaces, `.`, `_` and `-`,
  and can be at most 40 characters.
- **`layout_id`**: a string that is unique on the board. It appears in URLs, so no
  `/`, `?` or `#`. Use short readable ids such as `temperature-trend`. Quote ids
  that look like numbers (`'1'`), because an unquoted number is not a string and
  the editor would not show the widget.
- **`version`**: set it to the version `widget.py` printed. The board renders
  exactly the pinned version, so it should be the version whose schema you checked
  against. Without a pin, the platform uses the newest version at install time.
- **`chartconfig`**: only properties from the widget's definition schema. Unknown
  keys are silently ignored, so an invented key does nothing.
- **`custom_style`**: `text_color`, `tile_background_color`, `tile_border_color`
  and `tile_border_radius` (e.g. `8px`).

Start the file with the schema line shown above, like the other templates. The
editor rewrites the file when someone saves the board: it sorts widgets by
`layout_id` and pins versions, but keeps comments, including the schema line and
any comment above a widget. Older platform versions dropped comments on save, so
re-add the schema line if it has gone missing.

## Literal values

Write every constant in `chartconfig` with its type prefix, the way the editor
does:

| Value | Write |
|---|---|
| text | `$str:Line 3` |
| empty text | `'$str:'` |
| number | `$num:12.5` / `$num:0` |
| boolean | `$bool:true` / `$bool:false` |
| colour | `$str:#4caf50` |

The prefixes matter because:

- **Inside a tableRef `format`, an unprefixed string is a column name.** A constant
  there must carry a prefix. A raw number or boolean in a format makes the whole
  item null.
- **Outside a format, unprefixed values work.** When someone opens the widget in
  the editor and saves, a raw `false` or `0` is stored as `$bool:false` or
  `$num:0` and keeps its value. Studio 3.5.2 and earlier replaced a raw `false`,
  `0` or `''` with the widget's default.
- **The prefix is found anywhere in a string**, not only at the start. Never put
  `$str:`, `$num:` or `$bool:` inside a text such as a markdown body, because
  everything before the prefix would be cut off.

Long multi-line text such as `markdown: |` can stay unprefixed. To leave a setting
unset, omit the key rather than writing `null`.

Boards the editor saved also contain:

- **`'$num:'`, a number field someone cleared.** The board treats it as unset:
  the widget gets no value for the key and uses its own default, and in a list
  that item is `null`. Studio 3.5.7 and earlier read it as 0, so write `$num:0`
  for zero and omit the key for the default. `'$str:'`, by contrast, is a real
  empty text.
- **The settings each dropped widget starts with**, with their text, colour,
  number and boolean values prefixed. They are the
  widget's example (`widget.py <package> --example`), and a `0`, `false` or `''`
  among them is kept as `$num:0`, `$bool:false` or `'$str:'`. Studio 3.5.7 and
  earlier stored those three as `null`.

## Binding data

A property can hold a binding instead of a literal. The binding object has exactly
one key and replaces the whole value:

```yaml
value:                   # a single value  →  valueRef
    valueRef: {...}
data:                    # a list          →  tableRef
    tableRef: {...}
```

Use `widget.py` to see each property's type. **valueRef** goes where the schema
says string, number, boolean, color and so on. **tableRef** goes where it says
`array`, never as an element inside a list (`[ {tableRef} ]` is wrong). An object
property never takes a binding; bind its fields instead. Properties marked
`dataDrivenDisabled` take no binding at all.

### valueRef: one value

```yaml
valueRef:
    tablename: measurements    # a table or transform from data-template.yml
    column: temperature        # column id, or a json path: payload.sensor.value
    queryParams:
        limit: 1
```

This gives the newest value of the column after the filters are applied.
`queryParams` is optional (it defaults to `limit: 1`), but when present it needs a
`limit`.

### tableRef: a list

```yaml
data:
    tableRef:
        tablename: measurements
        format:                # one array item per row
            x: tsp
            y: temperature
            pivot: machine_id
        queryParams:
            limit: 500         # 1 to 3000; the newest rows are kept
```

- **`format` is the template for one array item.** It is shaped exactly like the
  `items` of that array in the widget's schema
  (`widget.py <pkg> --path dataseries.data`). For an array of objects it is an
  object. For an array of arrays, such as doughnut `sections`, it is a list.
- **Leaves are column ids or json paths**, or prefixed constants such as
  `iconName: $str:settings`. Only properties of the item are allowed.
- **Rows arrive oldest first.**
- **`pivot` splits the rows** into one series, gauge or doughnut per distinct
  value. For example, `pivot: machine_id` draws one line per machine. Gauges and
  value tiles split only with `multiChart: $bool:true`, and then read `data`
  instead of `value`. A doughnut becomes one separate chart per value, never
  nested rings; bind the same pivot column on every slice of its format.
- **`limit` is required.** Charts usually want 500 to 3000; a list of entities as
  many as you expect.

### queryParams

| Key | Meaning |
|---|---|
| `limit` | Maximum rows, 1 to 3000. Always set it. |
| `windowPeriod`, `windowLength`, `nowMinusPeriods` | Rolling time window, e.g. `hour`, `24`, `0` for the last 24 hours up to now. Periods: `second minute hour day week month year`. The window applies only when **all three** are set. |
| `timeStartParam`, `timeEndParam` | Names of URL parameters (a filter-calendar's `startKey`/`endKey`) whose values replace the window's start and end. They need a complete window. |
| `filterAnd` | List of filters, all of which must match. |
| `series` | Aggregation, see below. |

The order of application is: time window, then filters, then aggregation, then
limit. Never write `timeRange`, `columns` or `swarm_app_databackend_key`; the
platform derives or sets them.

### Filters

```yaml
filterAnd:
    - column: machine_id
      operator: '='              # quote it: a bare = breaks some YAML parsers
      value: press-1
      dataType: string           # the column's dataType from data-template.yml
```

- **Operators:** `= != <> > >= < <= LIKE ILIKE NOT LIKE NOT ILIKE IN NOT IN IS NULL
  IS NOT NULL IS CURRENT USER`, in uppercase. `IN` takes a list as its value, and
  `IS NULL` and `IS CURRENT USER` take no value.
- **The person viewing the board:** `operator: IS CURRENT USER` keeps the rows
  whose column (string or bigint) is the viewer's account id, the id the platform
  stamps as `authid` on every row a person saves. The data backend fills it in
  for each read, so a widget can show the viewer their own record or their own
  saves; a visitor who is not signed in sees no row. The column must exist on the
  table (or transform) the binding reads, and the operator does nothing in alarms.

  ```yaml
  # The viewer's own user record, e.g. their name in a header label
  - {column: account_id, operator: IS CURRENT USER, dataType: string}
  # Rows the viewer saved through a form
  - {column: authid, operator: IS CURRENT USER, dataType: string}
  ```
- **`dataType` is required in practice.** Without it, the database does not apply
  the filter.
- **Latest row per entity:** on a table with `maintainLatestFlagFor`, this filter
  keeps only the newest row of each entity:

  ```yaml
  - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
  ```

  The newest row is chosen by `tsp` each time the widget reads. On a table without
  an entity key, the filter keeps only the single newest row. Other conditions and
  the time window apply to those newest rows, so an entity whose newest row fails
  them is hidden. It is never replaced by an older row. There is no `latest_flag`
  column, so don't filter on one.

- **From the URL path:** `useRoute: true`, where `value` is the index of the route
  segment. On `/machines/press-1`, segment `'1'` is `machines` and `'2'` is
  `press-1`. See [Pages and navigation](#pages-and-navigation).
- **From a filter widget:** `useFilter: true`, where `value` is the URL parameter
  name, i.e. a filter-dropdown's `parameterKey`. When the parameter is absent, the
  filter is dropped, so the widget shows everything.
- **OR logic:** `{combinator: OR, filters: [ ... ]}`.
- **A filter that is off until the user switches it on.** An unset `useFilter`
  parameter removes its predicate, also inside a group. So put the switchable
  predicate into an OR group with the default condition. This table shows the
  records that are not deleted, until a widget-filter-dropdown with
  `parameterKey: $str:show_deleted` and the option
  `{label: $str:Show deleted, value: $str:true}` sets the parameter:

  ```yaml
  filterAnd:
      - combinator: OR
        filters:
            - {column: deleted, operator: 'IS NULL', dataType: boolean}
            - {column: deleted, operator: '=', value: false, dataType: boolean}
            - {column: deleted, operator: '=', value: show_deleted, dataType: boolean, useFilter: true}
  ```

### Aggregation

`series` makes the database compute one value per group instead of returning raw
rows:

```yaml
queryParams:
    limit: 3000
    windowPeriod: day
    windowLength: 7
    nowMinusPeriods: 0
    series:
        method: AVG              # AVG SUM COUNT MIN MAX FIRST LAST
        bucket:                  # optional: a fixed interval; omit for automatic
            length: 1
            period: hour         # second minute hour day week
```

The roles come from the format:

| Format | Result |
|---|---|
| `x: tsp` | A time series. Buckets are automatic (sized to the widget's width) or fixed by `bucket`. |
| `x: <other column>` | One value per category over the whole window. No `bucket`. |
| `pivot: <column>` | Each group aggregated separately, e.g. one line per machine. |
| every other column leaf | Aggregated with the method. |

Rules, which the validator enforces:

- Aggregation needs a complete time window. Without one, raw rows come back
  silently.
- `AVG` and `SUM` need numeric columns. `tsp` can only be counted: `y: tsp` with
  `COUNT` is the number of records.
- On a valueRef, aggregation means one value over the whole window. It needs
  `limit: 1` and no bucket. Example: readings today is
  `column: tsp, series: {method: COUNT}` with a 1-day window.
- There is one method per series. To show average and maximum, add two series.
- Transforms cannot be aggregated (see below).

## What a binding can and cannot read

You can read:

- **The app's own tables:** every column, plus `device_key` (the publishing device)
  and `authid`, which exist on every table. That includes tables and transforms
  marked `private: true`: users can't reach those directly, but the app's own
  board can. Users see whatever the board shows, so show only what they should see.
- **Transforms (SQL views):** only `limit`, `offset` and `filterAnd` work. There is
  no time window, no aggregation and no latest filter, and rows come in the view's
  own order.
- **`error-logs`:** the app's error log, with columns `tsp msg user_message source
  level device_key`. `source` is `app` for what the app reports with
  `report_error` and `system` for the platform's own errors, and `user_message` is
  the text for operators. A widget-toast shows the app's reports with `message`
  bound to `user_message` and `type` to `level`, both filtered on
  `{column: source, operator: '=', value: app, dataType: string}`. The toast knows
  the types `success`, `error`, `info` and `warning`; `report_error` sends `error`,
  `warning`, `info` or `debug`, and the toast shows `debug` as `info`. SDK versions
  before 1.10.0 sent `warn` for `warning`, which the toast shows as `info` too.
- **Another app's table:** add `provider_app: <app name in lowercase>` to the ref,
  and list that app under `consumes` in data-template.yml. Only that app's shared
  tables and transforms can be read. Its private ones are not shared.

There's no arithmetic, ratio, join or derived column in a binding, and no widget
computes those either. When a widget needs one, add a transform to
data-template.yml that computes it in SQL and bind to the transform. The same goes
for "latest value per machine, summed", or anything else that combines rows in a
way the aggregation table above cannot express.

## Pages and navigation

`layout` is a tree of pages:

```yaml
layout:                         # /
    gridLayout: [...]
    subRoutes:
        machines:               # /machines
            gridLayout: [...]
            subRoutes:
                '*':            # /machines/<anything>: one page for every machine
                    gridLayout: [...]
```

- **Page names** use letters, digits, `.`, `_`, `-` and `*`. A `*` page matches any
  segment, and the widgets on it read the segment with `useRoute` filters.
- **Every page needs a `gridLayout`.**
- **A widget is on a page** when that page's `gridLayout` has an entry whose `id`
  is the widget's `layout_id`.
- **Shared widgets:** to show the same widget on several pages (a menu, say), add
  the same id to each page. Give it the same position on every page, because moving
  it in the editor moves it everywhere.

### Every page is reached by clicking

People move through a board only by clicking: nobody types a route, and a kiosk
screen has no address bar. So:

- **Every page must be reachable from the home page** (`/`) through a series of
  clicks, and **every page must lead back home.** A page that nothing links to
  cannot be opened, and a page without a way back traps its user. The validator
  follows every link from the home page the way the board does, and reports each
  page it cannot reach, and each page with no way back, as an error.
- **Only navigation widgets move between pages:** widget-navbar, widget-sidenav and
  widget-navbutton. A widget-table `button` or `image` cell opens its link in a new
  browser tab, so it cannot move inside the board. Use those cells for external
  links only.
- **Put the same menu on every page of one level, at the same position**, so it
  reads as the board's menu. A parent page that exists only to hold `*` children
  (`/machines`) still needs content: make it the list that leads to them.

### How menu items are highlighted

widget-navbar and widget-sidenav highlight an item when **the current route starts
with the item's route**. A relative item (no leading `/`) is highlighted when the
current route ends with it. Three rules follow:

1. **Never give an item the home route.** Every route starts with `/`, so an item
   with the route `/` (or an empty route) is highlighted on every page, next to
   the item the user actually chose. Link home from the menu's **title** instead
   (`title: $str:Machine Monitor`, `route: $str:/`). The title is never
   highlighted.
2. **Never put an item whose route is a prefix of another item's route into the
   same menu**, such as `/line/*` next to `/line/*/andon`, or `/reports` next to
   `/reports/daily`: on the deeper page both are highlighted. The comparison is by
   characters, so `/line` even matches `/lines`.
3. **An item stays highlighted on the pages below its route.** `/machines/` is
   highlighted on `/machines/press-1` too. Use that: give each section one item,
   and connect the pages inside a section with their own links (see the patterns
   below).
4. **Data-driven menus inherit rule 2 from the data.** A menu built from a table
   with routes like `/line/<id>` lights up `LINE-1` on `LINE-10`'s pages, because
   `/line/LINE-10` starts with `/line/LINE-1`. The validator cannot see ids, so
   say in the key column's description (and the form that creates the record)
   that ids need the same number of digits: `LINE-01` … `LINE-24`.

widget-navbutton is never highlighted. That makes it the right widget for a single
link such as "Home", "Back to the list" or "Manage documents".

### How a link resolves

- **`/machines` is absolute**, from the board's home.
- **`press-2`, with no leading slash, replaces the last segment** of the current
  URL. From `/machines/press-1` it goes to `/machines/press-2`. From `/machines`
  (no trailing slash) it would go to `/press-2`. So link a page whose children are
  reached relatively with a trailing slash: `/machines/`.
- **A segment that is exactly `*`** is replaced by the current URL's segment at
  that position, and `{{name}}` by the item's `variables` entry with `label: name`.
  A `*` needs a segment at its position: on `/machines`, the route
  `/machines/*/trend` has no second segment to copy, so the link opens
  `/machines/trend`.
- **A route that contains `*` loses its trailing slash.** `/line/*/andon/` opens
  `/line/LINE-1/andon`, so relative links on that page lead next to it
  (`/line/LINE-1/<id>`), never below it. Below a `*` page, item routes have to be
  absolute (pattern 3).

### Navigation patterns

1. **Sections.** One widget-navbar or widget-sidenav on every page. Its title links
   home, and each item opens one section (`/machines/`, `/alarms`, `/settings`).

2. **A list and its detail pages** (`/machines` and `/machines/*`). A data-driven
   menu lists one item per row:

   ```yaml
   navItems:
       tableRef:
           tablename: machine_status
           format:
               label: machine_id
               iconName: $str:precision_manufacturing    # Material icon name
               route: machine_id                         # relative: /machines/<id>
           queryParams:
               limit: 50
               filterAnd:
                   - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
   ```

   Put this menu on `/machines` and `/machines/*`, and link to the list with a
   trailing slash and no `*`: `/machines/`. On the `*` page, filter every widget
   with `{column: machine_id, operator: '=', value: '2', dataType: string, useRoute: true}`.

3. **Detail pages below a `*` page** (`/line/*/andon/*`). A relative route cannot
   reach them (see above), and a binding cannot join strings. Compute the absolute
   route in a transform, and bind the item's `route` to it:

   ```yaml
   # data-template.yml: a column of the transform the menu reads
   sql: SELECT ..., '/line/' || line_id || '/andon/' || request_no AS route FROM ...
   ```

   ```yaml
   format:
       label: request_no
       route: route          # /line/<line>/andon/<request>
   ```

   Filter the menu by the route segment as usual; transforms accept `filterAnd`.
   The validator reads the transform's SQL to see which page such a route opens,
   so write it as `'/literal/' || column || ...` or `concat('/literal/', column, ...)`.

4. **An entity with an overview and sections** (`/line/*`, with `/line/*/andon`,
   `/line/*/reports` and so on below it). The overview cannot be an item next to
   its sections (rule 2). Make the menu's title the link to the overview (`title`
   bound to the entity's name, `route: $str:/line/*`), and put a widget-navbutton
   next to the menu as the way home (`title: $str:Home`, `iconName: $str:home`,
   `route: $str:/`).

5. **Pages within a section** (`/line/*/sop` and `/line/*/sop/manage`). Connect
   them with widget-navbutton ("Manage documents", "Back to documents"). The
   section's item stays highlighted on both.

6. **Records that users create, edit and delete** (master data, settings). A list
   page shows a table of the records, a "New" form (`formButton: $bool:true`) and a
   data-driven menu of the records (pattern 2 or 3) that opens one edit page per
   record (`/settings/machines/*`). The edit page holds a widget-form:
   - Its fields are prefilled from the record: `preFilledValue` is a valueRef with
     a `useRoute` filter on the record's key, and the key itself is a
     `hiddenField`, so a save updates that record.
   - `deleteButton: $bool:true` with `deleteFlagColumn` set to the table's
     soft-delete column. The form writes that column on every submit: `false` on
     Save and `true` on Delete, so saving a deleted record restores it. Give the
     "New" form the same `deleteFlagColumn`, so every row has the flag set.
   - `deleteNavigationRoute` leads back to the list, which the form opens after a
     delete.

   Hide deleted records by default, and let users show them with a filter that is
   off until it is switched on (see [Filters](#filters)).

### Filter widgets

Filter widgets set URL parameters for other widgets to read:

- **widget-filter-dropdown:** set `parameterKey: $str:machine`. Each widget it
  should filter needs a filter with `useFilter: true, value: machine`.
- **widget-filter-calendar:** set `startKey` and `endKey`. Each widget it should
  filter needs `timeStartParam` and `timeEndParam` with those names, plus a
  complete time window, which serves as the default range.

### Uploading files with a form

A widget-form field with `type: $str:file` uploads one file into a FleetFiles
namespace of the app and writes the stored file's key into its `targetColumn`, in
the same save as the rest of the row (widget-form 1.0.38 and later):

```yaml
- label: $str:SOP document
  type: $str:file
  required: $bool:true
  targetColumn: {tablename: sop_commands, column: file_key, dataType: string}
  fileNamespace: $str:sop                    # a name from files.namespaces
  acceptedFileTypes: $str:application/pdf    # MIME types; image/* works too
  maxFileSizeMB: $num:6
  fileSizeColumn: {tablename: sop_commands, column: size_bytes, dataType: bigint}
```

- The target is a string column. It gets the key within the namespace,
  `<YYYY-MM-DD>/<random>/<file name>`: the last segment is the original file name,
  extension included. The app's code reads the file with the SDK's files API under
  that key and namespace.
- `fileNamespace` must be in the app's `files.namespaces` in data-template.yml
  (with none declared, only `default` exists). Keep `acceptedFileTypes` within the
  namespace's `contentTypes` and `maxFileSizeMB` within its `maxObjectBytes`. The
  validator checks all three.
- Files up to 6 MB upload on every installation. Larger ones need a presigned
  upload, which an appliance cannot issue, so a board that runs on an appliance
  keeps `maxFileSizeMB` at 6 or below.
- `fileNameColumn` (string), `fileSizeColumn` (bigint or numeric) and
  `fileTypeColumn` (string) are optional, belong in the target column's table, and
  are written only with a new file.
- In an edit form (pattern 6), bind `preFilledValue` to the record's key column:
  the form shows that file, and a save without a new file keeps it.
- Uploading needs DATABACKEND UPDATE, like every form write. It does not work on an
  appliance opened through the cloud; there the form says to open the board on
  the appliance itself.

### Embedding a web UI the app serves

A device's own web page (a live view, a machine's HMI) reaches the board through
the remote-access tunnel of its port: the app writes the tunnel's URL into the
device's row of an entity table (app-architecture.md, "Web UIs on the device"),
and a widget-embed on the device's page reads it:

```yaml
webUrl:
    valueRef:
        tablename: devices                   # maintainLatestFlagFor: [device_key]
        column: ui_url
        queryParams:
            limit: 1
            filterAnd:
                - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                - {column: device_key, operator: '=', value: '2', dataType: numeric, useRoute: true}
```

- Put it on the `*` page of a device list (pattern 2), whose menu routes by
  `device_key`. The starter app's board in `assets/app-template/` has this page.
- Set `multiEmbed: $bool:false`. With `multiEmbed: $bool:true`, `data` takes a
  tableRef with the format `{url: ui_url, title: device_name}` and shows every
  device's page side by side, which suits a handful of devices.
- Only production installs have tunnels. A development run writes no URL, and its
  embed stays empty.

## Layout

The grid is `style.columns` × `style.rows`, by default 96 × 64. Positions are given
in cells: `x`, `y` from 0, and `w`, `h`. Without `overflow`, the whole grid is
scaled onto the screen, so the grid is the screen. The exception is a widget with a
fixed width or height (see below).

- **Fill every page completely.** Any cell no widget covers shows as empty screen,
  and users read that as unfinished. Plan bands whose heights add up to `rows` and
  split each band into widths that add up to `columns`. On a 96 × 64 grid:

  ```text
  nav    x=0  y=0  w=16 h=64 │ gauges x=16 y=0  w=52 h=24 │ power  x=68 y=0  w=28 h=24
                             │ trend  x=16 y=24 w=52 h=40 │ states x=68 y=24 w=28 h=40
  ```

- **Size for readability.** A chart below roughly 16 × 10 cells is too small to
  read. With few widgets, make them bigger rather than leaving space.
- **Give navigation bars a fixed size.** Normally, set `fixedWidth: true` on a
  sidebar's position (widget-sidenav) and `fixedHeight: true` on a top bar's
  position (widget-navbar). Without it, a bar scales with the screen: a sidebar
  grows wide on a large monitor and squeezes its labels on a laptop. With it, every
  column or row the bar spans is `style.cell_size` pixels (default 12) on any
  screen, and the other columns and rows share the rest. So `w: 16` gives a
  sidebar of about 190 px, and `h: 5` a top bar of about 60 px (minus
  `grid_gap`). Other widgets in those columns or rows get the same fixed size,
  which keeps a button beside the navbar in line with it.

  ```yaml
  - {id: nav, x: 0, y: 0, w: 16, h: 64, fixedWidth: true}     # widget-sidenav
  - {id: top, x: 0, y: 0, w: 96, h: 5, fixedHeight: true}     # widget-navbar
  ```

- **Let navigation blend in.** A widget-navbutton normally has no tile border, and
  often no tile background either, so it reads as a button and not as a tile with
  a button inside. Widgets in a top navbar band usually look better without a
  border too. This is a default, not a strict rule:

  ```yaml
  custom_style:
      tile_border_color: transparent
      tile_background_color: transparent   # optional
  ```

- **Keep everything inside the grid:** `x + w <= columns` and `y + h <= rows`.
- **Layering is allowed.** A small widget (a date picker, a button) may sit on top
  of a big one. `z` orders them, higher in front.

## Style

`style` applies to the whole board. Every key is optional:

```yaml
style:
    theme: {theme_name: light}   # --- light dark chalk essos halloween infographic macarons
                                 # purple-passion roma shine vintage walden westeros wonderland
    background_color: '#fefefe'
    text_color: '#334d5c'
    tile_background_color: '#ffffff80'
    tile_border_color: '#fefefe'
    tile_border_radius: 8px
    grid_gap: 8                  # pixels between tiles
    columns: 96
    rows: 64
```

`overflow: true` makes the board scroll (cells are then `cell_size` pixels) instead
of scaling to the screen.

## Markdown and HTML

widget-markdown renders Markdown and HTML. A `{{name}}` placeholder shows the value
of the `data` entry whose `label` is `name`:

```yaml
markdown: |
    <div style="background:{{stateColor}};border-left:4px solid #58a6ff;padding:8px 12px">
      <a href="/machines/{{machine}}">{{machine}}</a> is {{state}}
    </div>

    **Temperature:** {{temperature}} °C
data:
    - {label: $str:machine, value: $str:press-1}
    - {label: $str:state, value: $str:running}
    - label: $str:stateColor
      value:
          valueRef: {tablename: machine_status, column: state_color, queryParams: {limit: 1}}
    - label: $str:temperature
      value:
          valueRef: {tablename: measurements, column: temperature, queryParams: {limit: 1}}
```

From widget-markdown 1.0.14 on, a placeholder works in text, code, link addresses
and HTML attribute values (`style`, `class`, `href`, `src`), and in a `<style>`
element:

- **Values are plain text.** A value never becomes markup, so it cannot add a tag
  or leave its attribute. Markup in a value shows literally. Every placeholder
  needs a `data` entry with exactly its label, or it renders as nothing.
- **In CSS, a value must be a plain CSS value**, such as `#22c55e`,
  `rgb(34, 197, 94)`, `12px` or `bold`. This applies in a `style` attribute, a
  `<style>` element and an SVG `fill` or `stroke`. A value with `;`, `:`, quotes,
  braces or `url(` is left out. For a colour that follows the data, bind a column
  that holds the colour, for example a transform column
  `CASE state WHEN 'running' THEN '#22c55e' ELSE '#ef4444' END`.
- **An address must be http(s), mailto, tel or relative.** Images can also take
  `data:` images. Any other address is left out.
- **The widget runs no code.** It removes `<script>`, event handlers (`onclick=…`)
  and `javascript:` links. A placeholder can fill an attribute's value, but it
  cannot name a tag or an attribute.

Up to 1.0.13, a placeholder only worked in the text between tags. Inside a tag it
broke the tag, and the rest of the tag showed on the board as text. On those
versions, keep attributes fixed and use widget-signal or widget-label for colours
that follow the data.

For every version, HTML follows the rules of Markdown:

- **An HTML block runs from a line that starts with a tag to the next blank line.**
  Markdown inside the block is not parsed, so `**Status:**` keeps its asterisks.
  Use HTML there (`<strong>`, `<ul><li>`), or put a blank line between the HTML
  and the Markdown.
- **After a blank line, a line indented by four spaces or more is a code block.**
  This is also true inside a `<div>`, and the HTML of the line then shows as text.
  Write HTML without blank lines, or indent it by less than four spaces.
- **A `<style>` element styles only this widget.**

validate.py checks the markup against the version the widget pins, or the latest
version when it pins none.

## SCADA pages

widget-scada draws one industrial symbol (a tank, pump, valve, pipe and so on) per
widget, stretched to its tile:

- **Find symbols** with `widget.py widget-scada --symbols <word>`, which prints each
  symbol's id, natural size, aspect ratio (height/width) and bindings.
- **Read one symbol's settings** with `widget.py widget-scada --when symbol=<id>`.
- **Give each SCADA position** `aspectRatio: <the symbol's aspectRatio>`,
  `fixedWidth: true` and `fixedHeight: true`, as the editor does. Size it in the
  proportion of its `widgetSize`.
- **Put symbols on a page of their own.** Arrange them like the process, not like a
  tiled dashboard: a SCADA page does not need to fill the screen. Ask the user to
  check the proportions in the board editor, because grid cells are not square.

## Left to the board editor

Some values only exist inside a running platform, and a template cannot know them:

- **`actionApp` / `actionDevice`** in switch and SCADA actions are numeric keys of
  an app and a device. Leave them out, and tell the user to pick them in the editor.
  On a data-bound list of devices, `actionDevice` can come from the `device_key`
  column.
- **Uploaded images** (`useUpload`). Use an image URL instead, or let the user
  upload.

## Checklist

1. Every `tablename` and column exists in data-template.yml (or under
   `provider_app` in a consumed app), and the app's code actually publishes it.
2. Every chartconfig key comes from the pinned widget version's schema, and every
   constant is prefixed.
3. Bindings sit at the right kind of property (valueRef on single values, tableRef
   on lists), each tableRef has a `limit` and a `format` shaped like its items, and
   aggregations have a complete window.
4. Every page fills the grid. Every page can be reached from the home page by
   clicking and leads back to it, no menu item links to `/`, no item's route is a
   prefix of another item's in the same menu, and every route leads to a page.
5. Sidebars have `fixedWidth` and top navbars `fixedHeight`, and navbuttons have no
   tile border, unless there is a reason to do otherwise.
6. In widget-markdown, every `{{placeholder}}` has a `data` entry, values in CSS are
   plain CSS values, and the markup has no scripts or event handlers. HTML has no
   blank line followed by a line indented by four spaces or more.
7. `scripts/validate.py <app-dir>` (run it as SKILL.md shows) reports no errors.
