# Designing a board

This reference covers what to decide before a board gets its widgets, and the
rules for what goes on a page: the brief, what goes where, the one meaning of
each colour, and the look, with the three style presets. The checks to run on
the finished board before you report it are in board-critique.md. Which pages a board
has and how their routes are formed is in board-route-tree.md; the standard
shape of a board on which users manage assets is in board-assets.md.

Configuration fragments in this reference write constants with their type
prefix (`$str:`, `$num:`, `$bool:`). Whether a constant needs the prefix where
you write it is in the instructions of your surface; the fields and their
values are the same either way.

A board is glanced at, not studied. Before you place a widget, decide what the
board is for, and keep that decision where the next person who edits the board
finds it (your surface's instructions say where).

## The brief

Answer these before the first widget, each in a line or two:

- **Who looks at the board, where, and from how far.** Operators glancing at a
  wall screen in the hall from ten metres, a supervisor at a laptop, a
  technician on a tablet next to the machine. This decides the look, how many
  tiles a page can carry, and how big the numbers have to be.
- **What question each page answers.** The home page answers "is everything all
  right, and if not, where?". Every other page answers one question of its own:
  "how did press-1 run today?", "what are the settings?". A page with two jobs
  becomes two pages.
- **What people look for first.** On the home page that is usually a state (how
  many machines run, which one has a fault) or one headline figure. It gets the
  most prominent place and the biggest tile.
- **What users change on the board**, if anything: the settings a form writes,
  the functions a switch calls. Controls get a page or a corner of their own,
  never a place between the readings.
- **The states that matter and their colours** (see "One colour, one meaning"
  below).

A brief, written down:

```text
Viewers: operators on the wall screen in the hall, from the line (control-room
preset: dark, few big tiles); the shift supervisor opens it on a laptop too.
/          is every machine running? the states first, then the temperature
           and vibration trends and the power draw right now
/machine   the list; /machine/<machine> one machine's readings and its target speed
States: RUNNING green, IDLE grey, FAULT red, the same on every widget.
```

## What goes where

- **States first, then the headline figure, then trends, then detail.** Readers
  scan from the top left. The top band holds the states (widget-signal, or a
  short widget-table of one row per machine with its state, which is seen at a
  glance rather than read) and the headline figure (a widget-markdown card, or
  widget-gauge when the figure only means something against limits). Trends
  (widget-linechart, widget-statehistory) go below. Everything that has to be
  read rather than seen (tables of many rows or columns, forms, texts) goes on
  a page of its own.
- **Size follows importance.** What people look for first is the biggest tile
  on the page. Tiles of the same kind get the same size. A tile nobody can read
  from where they stand (a table or a form on a wall screen) does not belong on
  that page.
- **Fewer, bigger tiles.** A wall screen carries six to nine tiles, a tablet
  next to the machine six to eight. A page read at a desk carries up to about
  twelve. Beyond that, split the page by question
  and link the pages through the board's menu. Every page still fills its whole
  grid: a cell no widget covers shows as empty screen, and users read that as
  unfinished.
- **Text big enough for the distance.** Give text a font size of at least
  1/150 of the viewing distance, live values and states 1/120, titles and
  headline figures 1/80 (the minimum symbol heights of 16, 20 and 30 minutes
  of arc in FHWA-RD-98-057, chapter 3, with capitals at 0.7 of the font
  size). Convert with the screen's millimetres per CSS pixel: a live value
  read from 1 m needs 8.3 mm, 43 to 49 px on a 10 to 11 inch tablet (0.17 to
  0.19 mm per pixel) and 13 px on a 55 inch 1080p wall screen (0.63 mm). Set
  it with widget-label `fontSize`, widget-textbox `title.fontSize`,
  `subTitle.fontSize` and `body.fontSize` (CSS lengths, such as `24px`),
  widget-table `styling.headerFontSize` and `columns[].styling.fontSize`,
  widget-toast `fontSize`, widget-navbar and widget-sidenav
  `style.fontSize`, and in widget-markdown with container units
  (board-markdown.md), which grow with the tile.
- **One widget per data shape.** Choose the widget from the data, with the
  widget catalog: one figure, or figures that belong together → a
  widget-markdown card; a figure against limits → widget-gauge; a state →
  widget-signal; change over time → widget-linechart; states over time →
  widget-statehistory; several fields of many entities → widget-table; several
  fields of one record (an asset's current settings, the selected machine) →
  widget-markdown laid out in HTML; a text → widget-label. Never show the same
  value twice on one page.
- **One record is not a table.** Never use a widget-table for a result of one
  row, such as a tableRef with `limit: 1` or a filter on the record's key. A
  single row under a header line reads like a spreadsheet cell. Show the record
  as a widget-markdown card instead, laid out for what the record is (a
  settings card, a nameplate, a status panel), even when the user asked for "a
  table" of it, and say so when you report the board.
- **Figures are cards.** A KPI, one machine's current readings or a shift's
  output next to its target go into a widget-markdown card laid out for what
  they mean, with their context (what the figure counts, the unit, the period,
  the target or the time of the reading), not into widget-value tiles.
  widget-value is left for two cases: a figure that is the average of its
  latest readings (`advanced.averageLatest`), and one readout per distinct
  value of a column for however many there are (`multiChart` with `pivot`).
- **Repeat the same shape for the same thing.** One gauge per machine, all the
  same size, in one row, in the same order as the machine list and the table.

## One colour, one meaning

Colour on a board carries state, and in a chart which series is which. The
board's chrome (the four style colours) is neutral, chart series take the
series colours of board-charts.md, and a state colour appears only where it
means something:

- **Pick the four state colours once** (each preset below suggests a set) and
  write the same value for the same meaning into every widget: widget-signal
  `signals[].colorMap[].color`, widget-table `stateMap` (a string of pairs,
  `$str:'RUNNING': '#22c55e', 'IDLE': '#94a3b8', 'FAULT': '#ef4444'`),
  widget-statehistory `stateMap[].color`, widget-gauge
  `sections.sectionLimits[].sectionColor`, and widget-toast's severity colours.
  A fault that is red in the table and orange on the signal is two states to
  the reader.
- **Nothing else gets a state colour.** Text stays in the board's text colour
  (no `fontColor`, `valueColor` or `labelColor` unless the colour is a state),
  tiles keep the preset's tile colour (a widget's own `custom_style` colours
  only where a tile must blend in: navigation widgets, and the transparent
  tiles of buttons and dialog forms of board-assets.md), and decorative colours
  are left out. On a board where everything is coloured, nothing is an alarm.
  The alarm red also marks an action that destroys something: the Delete
  button and its dialog (board-interaction.md). On control-room it is
  `#f87171` there, a lighter red that keeps 3:1 on the raised dialog.
- **Limits are shown, not told.** A figure that has limits is a gauge whose
  sections carry the limits in the state colours. A legend such as "red =
  fault" is only needed where a state has no widget of its own.
- **Never colour alone.** A state shows as a word as well as a colour:
  widget-signal `signals[].colorMap[].statusLabel` for each condition
  ("Running", "Fault"). A widget-table `state` column draws only a coloured
  box: put a `string` column beside it, bound to the state in words that the
  app or a transform writes, never to the raw code (such as `TOO_HOT`). A
  badge in widget-markdown shows the state's word on its colour.
- **Colours in markup are frozen.** HTML in widget-markdown keeps the colours
  written into it on every theme, so a state colour goes in there only as a
  bound column (a column that holds the colour), never as a literal.

## Pick a look

Every board is built on one of the presets below. The preset is the basis of
the design decisions: the style values, the state colours, and how many tiles
a page carries. Choose it by the design direction: who looks at the board and
where, light or dark, and brand colours. `control-room` is for wall screens
and HMIs, `office` for desks and laptops, `daylight` for tablets and bright
halls.

Look for the direction before you ask for it. It can come from:

- the request, or what the user said earlier;
- the app: its description, and its other boards with their style (a board
  that sits beside them takes their preset unless the user asks for another
  look); an app for an HMI next to a machine, an andon board or a shop-floor
  display points at a wall screen or a panel;
- a brand the user or the app names, with its colours.

When none of these shows the direction, ask the user before you build: in your
reply, together with any other open question, or, where you cannot write to
the user yourself, as your surface's instructions say. Ask once per board, in
one question with concrete choices: the viewing situations, each naming its
preset and whether it is light or dark; an answer that leaves the choice to
you; and room for brand colours. When the user does not answer, or leaves the
choice to you, take `office`: most boards are opened at a desk or on a laptop.
Ask only for a new board or a restyle (a change to the look or the layout of a
whole board or page), never for a change that keeps the board's look, such as
what one widget shows. An answer, or no answer, settles the look: do not ask
again for that board.

When the user wants a dark board at a desk, or a light one on a wall screen,
take the preset of that theme that is closest to the viewing situation:
`control-room` for dark, `office` for light at a desk, `daylight` for light in
a bright place.

Copy the preset's style values whole into the board's style, and its state
colours into the widgets. On a restyle to another preset, the chart series
take that preset's series colours too (board-charts.md, "Colour"): the old
ones lose their contrast on the new tiles. A restyle of an existing board
keeps the board's grid (`columns` and `rows`), because its widgets are placed
on it. Brand colours go to the tile border or the navigation band, never to a
state; keep the preset's text and tile colours so the board stays readable.
When you report the board, say which preset you took and why: the user's
answer, what the request, the app or its other boards showed, or `office`
because nothing showed the direction.

The presets:

- **control-room**: wall screens and HMIs, read from a distance, often under
  harsh light. Dark, few tiles, big numbers.
- **office**: desks and laptops, a supervisor's or manager's overview with more
  tiles and tables. Light, soft contrast.
- **daylight**: tablets and panels next to the machine, bright halls, outdoors.
  Highest contrast, hard edges.

Their style values:

| Style key | control-room | office | daylight |
|---|---|---|---|
| `theme.theme_name` | `dark` | `light` | `light` |
| `background_color` | `#0f172a` | `#f1f5f9` | `#ffffff` |
| `text_color` | `#e2e8f0` | `#1e293b` | `#111827` |
| `tile_background_color` | `#1e293b` | `#ffffff` | `#f8fafc` |
| `tile_border_color` | `#334155` | `#e2e8f0` | `#9ca3af` |
| `tile_border_radius` | `8px` | `12px` | `4px` |
| `grid_gap` | `8` | `8` | `8` |
| `columns` × `rows` | 96 × 64 | 96 × 64 | 96 × 64 |

Their state colours, for the widgets:

| State | control-room | office | daylight |
|---|---|---|---|
| ok | `#22c55e` | `#16a34a` | `#15803d` |
| warning | `#f59e0b` | `#d97706` | `#b45309` |
| alarm | `#ef4444` | `#dc2626` | `#b91c1c` |
| idle | `#94a3b8` | `#64748b` | `#4b5563` |

Their series colours, for the charts (board-charts.md, "Colour", has the
rules; a restyle writes them into every chart):

| Series | control-room | office | daylight |
|---|---|---|---|
| 1st | `#60a5fa` | `#2563eb` | `#1d4ed8` |
| 2nd | `#e2e8f0` | `#1e293b` | `#111827` |

In every preset the text reads at 11:1 or better against the tiles and each
state colour at 3:1 or better, so they stay legible on cheap screens.
