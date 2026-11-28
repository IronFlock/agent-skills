# Data bindings

This reference covers how a widget of board-template.yml reads the app's data:
valueRef and tableRef, queryParams, filters (the latest row per entity, the
route, filter widgets, the delete flag), aggregation, what a binding can and
cannot read, the filter widgets that set URL parameters, and the widget-embed
binding that shows a device's web UI. It assumes the board's anatomy and the
literal prefixes (`$str:`, `$num:`, `$bool:`) from board-template.md, "Anatomy"
and "Literal values".

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

  The filter is live. The widget gets every new row of the table in realtime, in
  under a second, and a new row replaces the entity's previous row in the widget.
  So a table bound with this filter shows the current version of every entity,
  although the table keeps them all. No transform is needed for that, and one
  would only show the same rows later: on its schedule tick, or when the app's
  code refreshes it.

- **From the URL path:** `useRoute: true`, where `value` is the index of the route
  segment. On `/machines/press-1`, segment `'1'` is `machines` and `'2'` is
  `press-1`. See [board-navigation.md](board-navigation.md).
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

  With the latest filter in the same list, this is the live list of current
  records: a row with `deleted: true` removes its entity from the widget the
  moment it arrives, because the newest row per entity is picked first and this
  condition hides it afterwards. An older, undeleted row never comes back. Bind
  lists, menus and tables of records to the table this way, not to a transform.

- **Every list of a table with a delete flag filters on it.** When a table has a
  delete flag (a boolean `deleted` column, the column a delete form writes,
  board-assets.md), every widget that lists its entities hides the
  flagged ones: tables, sidenavs, navbar items, the options of a dropdown or of
  a form's dropdown field, markers on a map, any list. This holds for every list
  on the board, not only the one next to the edit form. Leave the filter out, or
  make it switchable as above, only where the user explicitly asks to see
  deleted entities.

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
        bucket:                  # a fixed interval: always for COUNT and SUM over time; otherwise omit for automatic
            length: 1
            period: hour         # second minute hour day week
```

The roles come from the format:

| Format | Result |
|---|---|
| `x: tsp` | A time series. Buckets are automatic (sized to the widget's width) or fixed by `bucket`; COUNT and SUM need a fixed bucket, at most 2,000 per window (board-charts.md). |
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
  no time window, no aggregation and no latest filter. The limit keeps the view's
  first rows, and the widget gets them in reverse order: a view ordered newest
  first arrives oldest first. board-charts.md, "Order", says how to order a
  ranking.
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
- **The project's alarms:** `provider_app: alarms`, with `alarms` or `*` under
  `consumes`. `alarms` holds one row per version of an alarm; bind it with
  `{latest: true}` (entity key `alarm_key`) for the current state of each alarm.
  `alarm_events` holds one row per status change, oldest first like every
  table. The validator knows both tables' columns (app-architecture.md,
  "Reading another app's data"). Neither can be a form's or a toolbar's target:
  only the platform writes them. A board reads production alarms, also while
  the app runs in development.

  ```yaml
  tableRef:
    tablename: alarm_events
    provider_app: alarms
    format: {time: tsp, alarm: display_name, status: to_status, device: device_name}
    queryParams:
      limit: 100
      windowPeriod: day
      windowLength: 1
      nowMinusPeriods: 0
  ```

There's no arithmetic, ratio, join or derived column in a binding, and no widget
computes those either. When a widget needs one, add a transform to
data-template.yml that computes it in SQL and bind to the transform. The same goes
for "latest value per machine, summed", or anything else that combines rows in a
way the aggregation table above cannot express. A transform reaches the board
on its schedule tick, or at once when the app's code calls `refresh_transform`
after writing the tables it reads (app-architecture.md, "Reading and writing
state with the SDK"). A filter on the table needs neither, so use a transform
only for what no filter can do. The current
row of each entity and the hiding of deleted records are filters (see above),
never a transform.

## Filter widgets

Filter widgets set URL parameters for other widgets to read:

- **widget-filter-dropdown:** set `parameterKey: $str:machine`. Each widget it
  should filter needs a filter with `useFilter: true, value: machine`.
- **widget-filter-calendar:** set `startKey` and `endKey`. Each widget it should
  filter needs `timeStartParam` and `timeEndParam` with those names, plus a
  complete time window, which serves as the default range.

## Embedding a web UI the app serves

A device's own web page (a live view, a machine's HMI) reaches the board through
the remote-access tunnel of its port: the app writes the tunnel's URL into the
device's row of an entity table (app-architecture.md, "Web UIs on the device"),
and a widget-embed on the device's page reads it:

```yaml
webUrl:
    valueRef:
        tablename: devices                   # maintainLatestFlagFor: [device_id]
        column: ui_url
        queryParams:
            limit: 1
            filterAnd:
                - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                - {column: device_id, operator: '=', value: '2', dataType: numeric, useRoute: true}
```

- Put it on the `*` page of a device list (board-navigation.md, pattern 2), whose items' routes are
  built from `device_id` (app-architecture.md, "Devices that register themselves"). The starter app's board in `assets/app-template/` has this page.
- Set `multiEmbed: $bool:false`. With `multiEmbed: $bool:true`, `data` takes a
  tableRef with the format `{url: ui_url, title: device_name}` and shows every
  device's page side by side, which suits a handful of devices.
- A development run writes the URL of its own tunnel (its label ends in `-dev`),
  which only users with the Develop privilege on the device can open.
