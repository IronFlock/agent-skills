# CLAUDE.md

Guidance for coding agents working on this IronFlock app.

TODO: describe in a sentence what this app does and for whom.

## Design

`design/` holds how this app is built and why: its purpose and users
(`design/README.md`), the architecture (`architecture.md`), the entity model
(`entities.md`), the board's design (`board.md`) and the decisions behind them
(`decisions.md`). Read it before changing the app, and update it in the same
change whenever the change makes a document wrong: a new table or column, a new
entity or relation, a new page or route, a new parameter, port or device
function, a different look. Record a choice between alternatives in
`decisions.md`.

## Rules

- Every column the code writes must exist in `data-template.yml`, and every row
  needs a `tsp`. The platform drops unknown keys and rows without `tsp` silently.
- Write a device's state only when it changes. On an entity table a row carries
  just the key, `tsp` and the changed columns; the others keep their values.
- A new kind of thing the app deals with is a new entity table
  (`maintainLatestFlagFor` on what identifies it), and the tables that refer to
  it carry its key. When users create and change it, the board gets its list
  bound to that table, a "New" form that opens in a dialog, and a detail page
  with the edit form and delete, as the `ironflock-templates` skill describes
  ("Boards that manage assets").
- The board reads an entity table's current state with the `{latest: true}`
  filter on the table itself, live: a new row replaces the entity's row in every
  widget. Records users delete get a boolean `deleted` column, and every widget
  that lists them (tables, sidenavs, dropdown options, map markers) filters on
  it unless the user explicitly asks to see deleted records. Never add a transform (a view) to pick the newest row per entity or
  to hide deleted rows; a transform refreshes on a schedule and would only show
  the same rows late.
- `publish_to_table` and `append_to_table` are the same call: each waits for a
  restarting data backend, up to the SDK's reconnect window, and returns once the
  row is stored. Send many rows at once with `append_rows_to_table`.
- After writing rows that a transform shown on the board reads, call
  `refresh_transform("<transform>")` once for the batch, so the board shows the
  change at once instead of at the transform's next scheduled refresh.
- Catch the SDK's `RuntimeError` around table writes in the main loop: a write
  raises when the platform has been unreachable for a minute, and the loop must
  keep running.
- `README.md` is the app's description in IronFlock, written for the people who
  install the app. Developer information goes here.
- After changing anything in `.ironflock/`, run the validator of the
  `ironflock-templates` skill (IronFlock's Claude Code plugin). Keep the
  `# yaml-language-server: $schema=` line at the top of every template.
- The board is also edited in IronFlock's board editor, which rewrites
  `board-template.yml`. Change the file in place; never regenerate it.

## Run

Push to the app's repository and run the app on a device from the IronFlock IDE.
That is a development run: it writes to the app's development tables, gets the
parameters' default values and a private tunnel for the live view, whose URL
(ending in `-dev`) `main.py` writes into `devices.ui_url`. Only users with the
Develop privilege on the device can open it, also from the IDE's side menu. On
the device's network the live view is at the address `main.py` prints when it
starts.
