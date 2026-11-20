# Designing a board

This reference covers what to decide before a board gets its widgets, and the
rules for what goes on a page: the brief, what goes where, the one meaning of
each colour, and the look, with the three style presets. Which pages a board
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
  widget-table with a state column) and the headline figure (a widget-markdown
  card, or widget-gauge when the figure only means something against limits).
  Trends (widget-linechart, widget-statehistory) go below. Everything that has
  to be read rather than seen (tables, forms, texts) goes on a page of its own.
- **Size follows importance.** What people look for first is the biggest tile
  on the page. Tiles of the same kind get the same size. A tile nobody can read
  from where they stand (a table or a form on a wall screen) does not belong on
  that page.
- **Fewer, bigger tiles.** A wall screen carries six to nine tiles. A page read
  at a desk carries up to about twelve. Beyond that, split the page by question
  and link the pages through the board's menu. Every page still fills its whole
  grid: a cell no widget covers shows as empty screen, and users read that as
  unfinished.
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

Colour on a board carries state and nothing else. The board's chrome (the four
style colours) is neutral, chart series take their colours from the theme, and
a state colour appears only where it means something:

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
  only on navigation widgets, so that they blend in), and decorative colours
  are left out. On a board where everything is coloured, nothing is an alarm.
- **Limits are shown, not told.** A figure that has limits is a gauge whose
  sections carry the limits in the state colours. A legend such as "red =
  fault" is only needed where a state has no widget of its own.
- **Colours in markup are frozen.** HTML in widget-markdown keeps the colours
  written into it on every theme, so a state colour goes in there only as a
  bound column (a column that holds the colour), never as a literal.

## Pick a look

Choose a preset by the viewing situation in the brief: `control-room` for wall
screens and HMIs, `office` for desks and laptops, `daylight` for tablets and
bright halls. Copy its style values whole into the board's style, and its state
colours into the widgets. Change the preset only when the user asks for brand
colours: give them to the tile border or the navigation band, never to a
state, and keep the preset's text and tile colours so the board stays
readable. When neither the request nor the app says where the board is looked
at, take `office`: most boards are opened at a desk or on a laptop. Ask only
when the app itself points at a wall screen or a tablet (an HMI next to a
machine, an andon board, a shop-floor display) and the request does not say.
Say which preset you chose and why when you report the board.

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

In every preset the text reads at 11:1 or better against the tiles and each
state colour at 3:1 or better, so they stay legible on cheap screens.
