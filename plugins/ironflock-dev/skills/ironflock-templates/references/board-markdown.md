# Markdown and HTML

This reference covers widget-markdown in board-template.yml: placeholders and
their `data` entries, what HTML may contain, HTML blocks, one record as a card,
how a value is shown, and figures as cards. When a card is the right widget is
in board-design.md, "What goes where". It assumes the board's anatomy and the
literal prefixes (`$str:`, `$num:`, `$bool:`) from board-template.md, "Anatomy"
and "Literal values". Each `data` entry binds its value with a valueRef
(board-bindings.md).

## Placeholders and HTML

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

On colours, for information: text without a colour of its own is drawn in the
board's text colour, so it suits light and dark boards alike. A colour written into
the markup (`style="color:#333"`) stays the same on every theme. That suits text on
a background the markup sets itself, such as a status badge, but on another theme it
can be hard to read.

Keep a status pill short ("In range", "2 alerts"). Put the affected names and
explanation in ordinary text that can wrap below it. Give the pill its own
padding on all four sides, in em so it grows with its label. Leave a gap to
adjacent text and let that text move to the next line.

## One record as a card

The fields of one record, such as the current settings of the machine a detail
page shows, go into a widget-markdown, never into a widget-table with one row.
validate.py warns about a widget-table whose every column yields one row
(board-design.md, "What goes where").
Bind each field with its own `data` entry, a valueRef with the filter the table
would have had, and write HTML that suits what the record is: a settings card, a
nameplate, a status panel. The name goes in a heading, units next to their values,
related fields in groups, and fields the reader does not need are left out.

```yaml
markdown: |
    <style>
    .rec {overflow-wrap:anywhere}
    .rec h3 {display:flex; flex-wrap:wrap; align-items:center; gap:.25em .5em; margin:0 0 .4em; line-height:1.25}
    .rec dl {display:grid; grid-template-columns:auto minmax(0,1fr); gap:.25em .75em; margin:0}
    .rec dt {opacity:.7}
    .rec dd {margin:0; font-weight:600}
    .rec .badge {display:inline-block; box-sizing:border-box; max-width:100%; padding:.25em .75em; line-height:1.25; border-radius:999px; color:#fff; background:{{stateColor}}}
    </style>
    <div class="rec">
    <h3>{{name}} <span class="badge">{{state}}</span></h3>
    <dl><dt>Setpoint</dt><dd>{{setpoint}} °C</dd><dt>Speed</dt><dd>{{speed}} rpm</dd><dt>Recipe</dt><dd>{{recipe}}</dd></dl>
    </div>
data:
    - label: $str:name
      value:
          valueRef:
              tablename: machines              # maintainLatestFlagFor: [machine_id]
              column: name
              queryParams:
                  limit: 1
                  filterAnd:
                      - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                      - {column: machine_id, operator: '=', value: '2', dataType: string, useRoute: true}
    # state, stateColor, setpoint, speed and recipe the same way, each on its own column
```

- **No text colours of its own.** Labels are set apart by `opacity`, so the card
  reads on light and dark boards. The badge sets its own background from a colour
  column, so its white text stays readable.
- **No blank lines inside the HTML**, so the Markdown rules above cannot turn a line
  into a code block.
- **Numbers get a format.** Give `setpoint` and `speed` `valueType: $str:number`
  and their `precision` (see "How a value is shown" below).

## How a value is shown

From widget-markdown 1.1.0 on, each `data` entry says how its value is shown.
validate.py rejects these keys on an older version.

- **`valueType`**: `$str:text` (the default) shows the value as given.
  `$str:number` rounds it to `precision` decimals (`$num:1` shows 23.456789 as
  23.5; the default is 0). `$str:timestamp` shows epoch milliseconds or ISO 8601
  as a date and time in the viewer's time zone and locale. A value that does not
  fit is shown as given. Give every measured number `$str:number`: as text, a raw
  reading shows all its decimals.
- **`tsp` and `maxLatency`**: bind `tsp` to the `tsp` column of the value's row
  (the same table and filter as the value) and set `maxLatency` in seconds, a
  few times the interval the device sends at. An older reading is left out: it
  shows as nothing, and a style or attribute that uses it is left out too, also
  while no new data arrives.
- **Text that follows the tile.** Use the tile's width and height to size a headline with `clamp()`, `cqw`
  and `cqh`. Keep labels and units readable at the smallest intended tile size.
  Allow for the widget's inset, a wrapped label, the widest expected reading and
  a localized timestamp. If these need another line, give the tile more room or
  move secondary detail to its detail page.

## Figures as cards

A figure goes into a widget-markdown card with its context: what it counts, the
unit, the period, the target or the time of the reading. Several figures that
belong together share one card.

```yaml
markdown: |
    <style>
    .kpi {overflow-wrap:anywhere}
    .kpi .v {font-size:clamp(1.25em,min(15cqw,32cqh),3em); font-weight:700; line-height:1.1}
    .kpi .u, .kpi .c {opacity:.7}
    </style>
    <div class="kpi">
    <div class="c">Power draw, press-1</div>
    <div><span class="v">{{power}}</span> <span class="u">kW</span></div>
    <div class="c">measured {{measured}}</div>
    </div>
data:
    - label: $str:power
      valueType: $str:number
      precision: $num:1
      maxLatency: $num:60
      value:
          valueRef:
              tablename: measurements
              column: power_kw
              queryParams:
                  limit: 1
                  filterAnd:
                      - {column: machine_id, operator: '=', value: press-1, dataType: string}
      tsp:
          valueRef:
              tablename: measurements
              column: tsp
              queryParams:
                  limit: 1
                  filterAnd:
                      - {column: machine_id, operator: '=', value: press-1, dataType: string}
    - label: $str:measured
      valueType: $str:timestamp
      value:
          valueRef:
              tablename: measurements
              column: tsp
              queryParams:
                  limit: 1
                  filterAnd:
                      - {column: machine_id, operator: '=', value: press-1, dataType: string}
```

- **widget-value only for averages and generated readouts.** Use it when the
  figure must be the average of its latest readings (`advanced.averageLatest`),
  or when one readout per machine is generated from a column for however many
  machines there are (`multiChart` with `pivot`): a card has a fixed set of
  entries.
