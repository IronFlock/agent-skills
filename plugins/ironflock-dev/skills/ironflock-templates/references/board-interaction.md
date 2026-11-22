<!-- Adapted from the skills ux-copy and accessibility-review of the design plugin, version 1.2.0, and from the frontend-design plugin, version 1.1.1, both by Anthropic, under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten for the settings of IronFlock board widgets. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-templates (IronFlock/agent-skills), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# Boards people act on

The words, sizes and contrast of what people click. The forms are in
board-assets.md, colours and presets in board-design.md.

## Words

- **A button says what its click does**: verb and object ("Save limits";
  the verb alone if the title names the object), never "Submit", "OK"
  or "Reset". In German the object comes first ("Grenzwerte speichern").
  widget-form `buttonLabels.submitLabel`, `buttonLabels.resetLabel`,
  `formButtonStyle.label`. No `save` icon (a floppy disk) as
  `formButtonStyle.iconName`.
- **One word for one thing** on every page: menus, titles, buttons,
  widget-table `columns[].header`, messages.
- **A form's `title` names the task** ("New machine"). In a dialog it is the
  headline and the round button's name; `subTitle` shows only in a tile.
- **Field labels** (`formFields[].label`) name the value and its unit
  ("Maximum temperature (°C)"), never a column name. `description` says
  what the user cannot know: the range, a format, what follows. `required`
  only on what the record needs; with `validation`, a `validationMessage`
  that says what to enter.
- **A delete states its consequence.** The delete form of board-assets.md,
  with what follows, as a fact, in the `description` of a `formFields`
  entry of type `section`, which writes nothing ("It leaves every list. Its recorded data is
  kept."). Write "cannot be undone" only when nothing brings it back. After
  the delete, `submitNavigationRoute` opens the list.
- **A switch acts at once.** Use widget-switch only where switching back
  undoes the action. A command that cannot be undone stays off the board,
  and the user is told why. Bind `dataseries[].value` to the state the
  device reports, so a failed command shows as the switch going back.
- **A message says what happened and what follows** ("Press 3 stopped: oil
  pressure low. Line 2 waits."). widget-toast shows `message` and
  `type` from rows the app writes. No codes, table or service names, no
  apology, no "Try again": say what the user can do.
- **An empty tile says why and what to do**: widget-label `emptyText`; next
  to a list that can be empty, a widget-markdown hint.

## Sizes on a board people touch

Only for touch screens. A finger needs 48 CSS pixels (8 to 9 mm on a 10 to
11 inch tablet). Set widget-form `formButtonStyle.size` `large` and
`fieldLayout.density` `comfortable`, widget-switch `size` `big`,
widget-navbutton `style.fontSize` 20 or more, widget-sidenav
`style.fontSize` 22, and on widget-table edit columns
`columns[].styling.fontSize` `24px`.

Give a button's tile `fixedWidth` and `fixedHeight`, a switch's
`fixedWidth`: their cells are then `cell_size` (12) px on every screen. Per
axis the tile needs ceil((control + 16 + grid_gap) / cell_size) cells, at
the default gap of 8 ceil((control + 24) / 12): 10 × 10 for the large round
button; for a large button with text 7 rows and ceil((label + 112) / 12)
columns, about 9 px per character. Recount them when `grid_gap` changes. A
"New" button on a list gets its own band above the list, not over its
items.

## Contrast

- Text needs 4.5:1 (from 24 px, or 19 px bold, 3:1), state colours, icons
  and field outlines 3:1; the presets meet this (`lobby` only over a dark
  picture, board-design.md).
- A brand colour behind text needs 4.5:1 with that text: widget-sidenav
  and widget-navbutton `style.backgroundColor` with `style.color`, a
  widget-navbar's `custom_style.tile_background_color` with
  `custom_style.text_color`. As widget-form `accentColor`, 3:1 against
  the tile.
- The Delete button and its dialog take the alarm red as
  `formButtonStyle.bgColor` and `accentColor`: `#b91c1c` on daylight,
  showroom, scada-grey and portal, `#dc2626` on office, `#f87171` on
  control-room and night-shift, `#fc8181` on lobby. Leave
  `formButtonStyle.color` unset on a button with text; the widget picks
  black or white.
