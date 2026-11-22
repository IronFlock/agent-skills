# Layout and style

This reference covers the grid of each page in board-template.yml (positions,
filling the grid, fixed-size widgets, navigation tiles, layering) and the
board's `style` (theme, colours, tile frames, background, the presets in the
file). Which preset suits a board and the state colours that go with it are in
board-design.md, "Pick a look". It assumes the board's anatomy and the literal
prefixes (`$str:`, `$num:`, `$bool:`) from board-template.md, "Anatomy" and
"Literal values".

## Layout

The grid is `style.columns` × `style.rows`, by default 96 × 64. Positions are given
in cells: `x`, `y` from 0, and `w`, `h`. Without `overflow`, the whole grid is
scaled onto the screen, so the grid is the screen. The exception is a widget with a
fixed width or height (see below).

- **Fill every page completely.** Any cell no widget covers shows as empty screen,
  and users read that as unfinished. Plan bands whose heights add up to `rows` and
  split each band into widths that add up to `columns`. On a 96 × 64 grid:

  ```text
  nav    x=0  y=0  w=16 h=64 │ states x=16 y=0  w=44 h=36 │ gauges x=60 y=0  w=36 h=36
                             │ trend  x=16 y=36 w=56 h=28 │ power  x=72 y=36 w=24 h=28
  ```

- **Size for readability.** A chart below roughly 16 × 10 cells is too small to
  read. With few widgets, make them bigger rather than leaving space.
- **Give fixed-size widgets their size.** A widget whose catalog entry or
  `widget.py` output has a **Layout** line keeps a fixed height or width (a
  dropdown filter is about 48 px tall, a sidebar about 184 px wide). Set that
  flag on its position, `fixedHeight: true` or `fixedWidth: true`, and give the
  fixed axis `ceil((px + grid_gap) / cell_size)` cells; `widget.py` prints the
  number for the default style. Without the flag the widget scales with the
  screen: a sidebar grows wide on a large monitor and squeezes its labels on a
  laptop. With it, every column or row it spans is `style.cell_size` pixels
  (default 12) on any screen, and the other columns and rows share the rest.
  Other widgets in those columns or rows get the same fixed size, which keeps a
  button beside a navbar in line with it. The validator warns about a missing
  flag or too few cells.

  ```yaml
  - {id: nav, x: 0, y: 0, w: 16, h: 64, fixedWidth: true}     # widget-sidenav, 184 px
  - {id: site, x: 16, y: 0, w: 20, h: 5, fixedHeight: true}   # widget-filter-dropdown, 48 px
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
    background_gradient_color: '#dfe6f5'   # optional: gradient from background_color to it
    background_gradient_angle: 135         # degrees, 180 is top to bottom
    text_color: '#334d5c'
    tile_background_color: '#ffffff80'
    tile_border_color: '#fefefe'
    tile_border_radius: 8px
    tile_style: outline          # frame of the tiles, see below
    tile_style_strength: 50      # strength of its shadow, edge or glow, 0-100
    grid_gap: 8                  # pixels between tiles
    columns: 96
    rows: 64
```

`tile_style` is what bounds the tiles:

- `outline` (the default): a 1 px line in `tile_border_color`.
- `shadow`: a faint hairline and a soft shadow below the tile, the card look of
  current interfaces. Cards look best on a page that differs from them: an opaque
  `tile_background_color` and a `background_color` a shade darker (lighter, on a
  dark board), with a `tile_border_radius` of 12px or more and a `grid_gap` of 12
  to 16.
- `flat`: neither line nor shadow. A tile shows by its background alone.
- `light-edge`: a line that is bright at the top and fades down the sides, as if
  lit from above. Made for dark boards, where a shadow does not show.
- `gradient-border`: a line in `tile_border_color` that is bright at the top
  left and fades out diagonally.
- `glow`: a line and a halo in `tile_border_color`. For dark boards; use it
  sparingly, it suits single widgets (an alarm in red) better than a whole board.
- `glass`: the tile blurs the board behind it and gets a bright edge and a soft
  shadow. It only shows on a board with something behind the tiles, a
  `background_gradient_color` or a `background_image`, and with a see-through
  `tile_background_color` (about 25% alpha, e.g. `'#ffffff40'` or `'#1e202940'`).
  The blur costs rendering time on every tile: leave it out for boards that run
  on weak panel PCs.

`tile_style_strength` sets how strong the shadow, the edge, the glow or the blur
is, from 0 (faint) to 100 (strong); the default is 50. `shadow` and `light-edge` do not
use `tile_border_color`; `gradient-border` and `glow` are drawn in it, so give it an
accent colour that shows on the background. `shadow`, `glow` and `glass` reach
beyond the tile: use them with grid snap on.

`background_image` is the address of an image that covers the board, above the
colour and the gradient. A template can only name an image that is already
online (an `https://` address); uploading one is done in the board's style
settings, and such an upload is served to signed-in members only. Keep
`background_color` close to the image's overall tone: the text colour and the
shadows are chosen against it.

A widget can take another frame with `custom_style.tile_style`, and give it a
strength of its own with `custom_style.tile_style_strength` (without one the
board's applies). Without a `tile_style` of its own, a
widget whose `custom_style` has its own `tile_border_color` stays an outline tile
on any board, and one with a transparent `tile_background_color` has no frame. So
the borderless buttons from "Let navigation blend in" (Layout, above) look the same under every
`tile_style`.

`overflow: true` makes the board scroll (cells are then `cell_size` pixels) instead
of scaling to the screen.

A style that names only a theme takes its four colours from the theme (its
background, title text and axis line colours), so `theme: {theme_name: dark}`
alone renders dark tiles. Set all four colours anyway: then the board looks the
same after a theme update, and the board editor stores all four on every save.
Without `style`, the platform defaults apply: `#fefefe` background, `#1a1430`
text, `#ffffff80` tiles with a `#fefefe` border.

### Presets

Three presets, `control-room`, `office` and `daylight`, each a complete `style`
block plus the four state colours for the widgets, are in
[board-design.md](board-design.md), "Pick a look", with the situation each one
is for and its values. Pick one by the viewing situation, copy all its values
into `style`, and change it only when the user asks for brand colours. The
control-room preset, as it stands in the file:

```yaml
style:
    theme: {theme_name: dark}
    background_color: '#0f172a'
    text_color: '#e2e8f0'
    tile_background_color: '#1e293b'
    tile_border_color: '#334155'
    tile_border_radius: 8px
    grid_gap: 8
    columns: 96
    rows: 64
# states: ok '#22c55e'  warning '#f59e0b'  alarm '#ef4444'  idle '#94a3b8'
```

[example-board.yml](example-board.yml) carries the office preset.
