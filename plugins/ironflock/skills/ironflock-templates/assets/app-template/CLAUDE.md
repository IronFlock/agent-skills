# CLAUDE.md

Guidance for coding agents working on this IronFlock app.

TODO: describe in a paragraph what this app does and for whom.

## How it is built

The program in `main.py` runs in a container (`Dockerfile`) on every device the
app is installed on. `.ironflock/` connects it to the platform.

- **The tables are the backend.** `.ironflock/data-template.yml` declares them,
  and the program reads and writes them with the `ironflock` SDK. The container
  keeps no state of its own: whatever the board, another device or a restarted
  container needs is in a table.
- **One writer per table**, named in the table's description: each device writes
  its own rows of `devices` and `measurements`, the board's settings form writes
  `settings`.
- **The board is the user interface** (`.ironflock/board-template.yml`): widgets
  bound to the tables, updated live. The board and the devices never call each
  other, so either works while the other is offline.
- **Settings reach the devices as rows.** `main.py` subscribes to `settings`,
  reads its newest row once at start, and applies a row only if it is newer than
  the one in force. The SDK (`ironflock` 1.10.0 or later) delivers the rows saved
  while a device was offline as soon as it is back, so the code never deals with
  connections or sessions.
- **The live view** is a web page `main.py` serves on port 8080
  (`web/index.html`, updated over a websocket). `.ironflock/port-template.yml`
  offers the port as a remote-access tunnel, `main.py` writes the tunnel's URL
  into `devices.ui_url`, and the board embeds that URL on each device's page.
  The port is in `main.py` (`UI_PORT`) and in `port-template.yml`: change both.

## Rules

- Every column the code writes must exist in `data-template.yml`, and every row
  needs a `tsp`. The platform drops unknown keys and rows without `tsp` silently.
- Write a device's state only when it changes. On an entity table a row carries
  just the key, `tsp` and the changed columns; the others keep their values.
- Append what must not be lost (state changes, records) with `append_to_table`:
  it waits for a restarting data backend. Publish high-rate readings with
  `publish_to_table`, which waits only for the connection: a row published while
  the data backend restarts is lost.
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
parameters' default values and no remote-access tunnel. Open its live view on
the device's network, at the address `main.py` prints when it starts.
