# board-template.yml

The board is the app's dashboard. The platform installs it into every project the
app is installed in, and binds its widgets to that project's copy of the app's
tables. Developers usually build it in the board editor of the IronFlock studio,
which reads and writes this file. Writing it by hand is fine, and the editor picks
up your version.

Structure is defined by `schemas/board-template/v1.yml`. Each widget's own settings
are defined by its published definition schema (`scripts/widget.py <package>`).

## Which file to read

The board's reference is split by task, so that a change reads only what it
needs. Every task needs this file: its [Anatomy](#anatomy) and
[Literal values](#literal-values), and its [Checklist](#checklist) before you
run the validator. Beyond that, read only the files your task needs: the
table in step 6 of the skill's SKILL.md names them for each task.

What each file holds:

- [board-design.md](board-design.md), [board-route-tree.md](board-route-tree.md)
  and [board-assets.md](board-assets.md): the design rules (the brief, what
  goes where, colours, the look and its presets; the route tree; boards that
  manage assets). They describe boards, pages and widget settings and hold for
  every way a board is built, so their fragments are JSON, which is valid YAML
  as it stands.
- [board-bindings.md](board-bindings.md): valueRef, tableRef, queryParams,
  filters, aggregation, what a binding can and cannot read, filter widgets,
  embedding a web UI the app serves.
- [board-navigation.md](board-navigation.md): the page tree, reachability,
  highlighting, how a link resolves, the navigation patterns.
- [board-forms.md](board-forms.md): the file side of boards that manage
  records: the delete form in YAML, uploading files and photos with a form.
- [board-layout-style.md](board-layout-style.md): the grid, fixed-size
  widgets, layering, the `style` keys, tile frames, the presets in the file.
- [board-markdown.md](board-markdown.md): widget-markdown placeholders and
  HTML, one record as a card, how a value is shown, figures as cards.
- [board-charts.md](board-charts.md): charts: when a chart and when a card,
  the order of ranked categories, scales, how many series, titles and axis
  labels, the series colours per preset.
- [board-interaction.md](board-interaction.md): the words on buttons, forms,
  confirmations, switches, messages and empty tiles; touch sizes and tiles;
  contrast of controls and brand colours behind text.
- [board-critique.md](board-critique.md): five checks to run once on a
  finished or restyled board before you report it, with one round of
  corrections.
- This file: [Anatomy](#anatomy), [Literal values](#literal-values),
  [Designing a board](#designing-a-board) (where the design is written, a
  sketch on a design canvas), [SCADA pages](#scada-pages),
  [Left to the board editor](#left-to-the-board-editor) and the
  [Checklist](#checklist).

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
      version: 1.1.39                # pin the version whose schema you used
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
- **`custom_style`**: `text_color`, `tile_background_color`, `tile_border_color`,
  `tile_border_radius` (e.g. `8px`), `tile_style` (the tile's frame, board-layout-style.md, "Style") and
  `tile_style_strength` for that frame.

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

## Designing a board

The design rules are in three references of their own. They describe boards,
pages, routes and widget settings, and hold for every way a board is built:

- [board-design.md](board-design.md): the brief, what goes where on a page,
  one colour for one meaning, and the look, with the eight style presets.
- [board-route-tree.md](board-route-tree.md): the route tree, how the pages
  and routes follow the entity model (app-architecture.md, "The entities"),
  and how menus and tab bars build their routes.
- [board-assets.md](board-assets.md): the one familiar shape of boards that
  manage assets: the asset types as the main menu, each type's list with a
  "New" button on top, the edit and delete forms, detail and tab pages,
  sub-assets, and the tiling of an asset's page.

Read board-design.md and board-route-tree.md before you place the first
widget, and board-assets.md before a board gets a list, a form or a detail
page of an entity users manage. Their configuration fragments are written as
JSON, which is valid YAML as it stands. This section says how the design goes
into the app's files.

### Where the design is written

The full design goes into the app's `design/board.md` (app-architecture.md,
"The design folder"): the brief, the route tree with what each page shows and
offers, the band plan of each page, the look. The comment header at the top of
board-template.yml, under the schema line, carries the short version (the
brief and the route tree, one line each) and points to `design/board.md`, so
someone who opens only the template in the board editor finds it too. Keep the
two in step.

Answer the questions of the brief (board-design.md, "The brief") in
`design/board.md`, and in the header one line each:

```yaml
# yaml-language-server: $schema=https://ironflock.com/schemas/board-template/v1.yml
# Board of machine-monitor, bound to measurements and machine_status.
# Design: design/board.md (keep both in step).
# Viewers: operators on the wall screen in the hall, from the line (control-room
# preset: dark, few big tiles); the shift supervisor opens it on a laptop too.
# /           is every machine running? the states first, then the temperature
#             and vibration trends and the power draw right now
# /machines   the list; /machines/* one machine's readings and its target speed
# States: RUNNING green, IDLE grey, FAULT red, the same on every widget.
```

Write the route tree (board-route-tree.md) into `design/board.md`, one line
per route with the page's name, what it shows and its main action, and its
short form into the header. Then build the pages one by one, each answering
its line. The video analytics tree of board-route-tree.md, "An example", as it
stands in the header:

```yaml
# /                                  Now: summary strip, snapshot wall, streams needing attention, latest events
# /stream                            Streams: all streams on all devices, "Add stream" (device in the form)
# /stream/<stream>                   Stream: live view, its device, zones table, recent events
#   .../zone                         Zones and lines: click to draw, "New line or zone"
#   .../zone/<zone>                  Zone: draw the zone, edit form, "Delete"
#   .../events                       the stream's events: date filter, events table, crossings charts
#   .../settings                     Stream settings: basic and advanced forms, "Delete stream"
# /detections                        Detections: crossings and occupancy on all devices, events
# /model                             Models: standard and custom models, "Register a custom model"
# /model/<model>                     Model: details, readiness per device
# /model/<model>/settings            custom model settings (custom models only)
# /device                            Devices: the list of devices, when each last reported
# /device/<device>                   Device: detected cameras, the streams it runs, "Remove device"
# /device/<device>/details           technical details (experts)
# Route segments: stream, model and device '2', zone '4'.
```

In `layout`, each type segment is a named page under `subRoutes`, and each
`<key>` is a `'*'` page below it (`stream` → `'*'` → `zone` → `'*'`).
[board-navigation.md](board-navigation.md) has the patterns that turn the
tree into menus and tab bars.

### Sketch it first, when there is a canvas

When the user wants to see the board before it exists, or asks for a mockup or a
design, and your environment has a design canvas (in Claude Code, the Artifact
tool's Design type), draw a wireframe before writing YAML:

- **One artboard per page, 1440 × 960 px.** That is the 3:2 of the default
  96 × 64 grid, so one cell is 15 px. Draw each tile as a rectangle at its grid
  position (`x`, `y`, `w`, `h` times 15), in the preset's tile colour with the
  preset's border on the preset's background, and write into it the widget type,
  the title and the table and column it binds
  (`widget-gauge · Temperature · measurements.temperature`). Signals and gauge
  sections take the state colours.
- **One swatch artboard.** The four board colours and the four state colours as
  labelled squares, each with the style key or the state it stands for.
- **Nothing a widget cannot render.** No typography, shadows, icons or components
  of your own. The artboard is the plan for the grid, not a picture to rebuild in
  widget-markdown.

Show it, take the user's changes on the artboard, then transcribe the approved
artboard tile by tile (`x = left / 15`, `w = width / 15`, rounded to whole cells)
and the swatches into `style` and the widgets' colour keys. Without a canvas, or
when the user did not ask to see the board first, write the band plan in text (as
in board-layout-style.md, "Layout") and go on. The sketch never blocks the work.

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
3. Bindings (board-bindings.md) sit at the right kind of property (valueRef on single values, tableRef
   on lists), each tableRef has a `limit` and a `format` shaped like its items, and
   aggregations have a complete window. Entity tables are bound with
   `{latest: true}`, and every list of a table with a delete flag (tables,
   sidenavs, navbar items, dropdown options, map markers) filters on that flag
   unless the user explicitly asked to see deleted entities. No transform
   deduplicates or cleans them.
4. The header holds the route tree (board-route-tree.md), and `layout`
   follows it (board-navigation.md): every key segment
   comes after a type segment, a child's pages sit below its parent's key, each
   entity has one page, and its aspects (events, settings, details) are pages
   below it. Every page fills the grid. Every page can be reached from the home
   page by clicking and leads back to it, and every route leads to a page. The
   items of every data-driven menu have absolute routes built from the row's
   keys with `format.variables`, never the key column alone. Menus
   pin widget-navbar and widget-sidenav 1.0.26 or later, and no two items of a
   menu share a route; on an older version, no item links to `/` and no item's
   route starts another item's in the same menu.
5. Every widget with a Layout line has its `fixedHeight` or `fixedWidth` and
   enough cells for it, and navbuttons have no tile border, unless there is a
   reason to do otherwise (board-layout-style.md, "Layout").
6. `design/board.md` holds the board's design and matches the board; the header
   says who looks at the board and where, and which look was chosen.
   `style` holds a preset's values whole (board-design.md, "Pick a look"),
   brand colours only where that section allows them. Every state colour means one
   thing on every widget, and nothing else is coloured (board-design.md;
   the `style` keys in board-layout-style.md).
7. In widget-markdown (board-markdown.md), every `{{placeholder}}` has a `data` entry, values in CSS are
   plain CSS values, and the markup has no scripts or event handlers. HTML has no
   blank line followed by a line indented by four spaces or more. No widget-table
   shows a single record: one record is a widget-markdown card. Figures are
   widget-markdown cards with `valueType: $str:number` and a `precision`, live
   readings with `tsp` and `maxLatency`; widget-value only averages or generates
   one readout per value of a column (board-design.md, "What goes where").
8. `scripts/validate.py <app-dir>` (run it as SKILL.md shows) reports no errors.
