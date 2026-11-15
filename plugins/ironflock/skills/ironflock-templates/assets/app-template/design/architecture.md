<!-- TODO: rewrite for this app (see design/README.md). -->

# Architecture

## The parts

| Part | Where it runs | What it does |
|---|---|---|
| `main.py` in a container (`Dockerfile`) | every device the app is installed on | reads the machine, keeps the device's state and readings in the app's tables, applies the settings, serves the live view |
| The app's tables (`.ironflock/data-template.yml`) | the project's database | hold all state: the devices, their readings, the settings |
| The board (`.ironflock/board-template.yml`) | IronFlock, in the browser | the app's user interface, bound to the tables live |
| The live view (`web/index.html`) | served by `main.py` on port 8080 | the machine's readings as they are taken, embedded in the board through the device's remote-access tunnel |

The program and the board never call each other. Both read and write the
tables, so either works while the other is offline.

## Tables and their writers

| Table | Kind | Written by | Read by |
|---|---|---|---|
| `devices` | entity table, keyed by `device_id` | each device, about itself: its registration at start, its state when it changes, its live view's URL; the board's delete form, `deleted` only | the board: device list, states, live view |
| `measurements` | readings, one row per reading | each device | the board: trends and current values |
| `settings` | one row per save; the newest is in force | the board's settings form | every device, which applies it |

One writer per table. Every row has a `tsp`.

## Data flows

1. **Readings:** every `SAMPLE_INTERVAL` seconds a device reads its machine and
   appends a row to `measurements`. The board's charts follow the table live.
2. **State:** a device writes a row to `devices` only when its state changes
   (OK, TOO_HOT, NO_READING). The board shows the newest row per device with the
   `{latest: true}` filter and the filter on `deleted`.
3. **Registration and deletion:** at start a device writes its row with
   `device_id`, its name, its live view's URL and `deleted: false`. A device
   cannot unregister, since it cannot tell being offline from being gone, so
   users delete a device that is gone with the "Delete" button on its page,
   which writes `deleted: true`. The state rows leave `deleted` out and keep a
   deletion in force; a device that starts the app again reappears.
4. **Settings:** the board's form appends a row to `settings`. Every device
   follows the table with `subscribe_to_table`, reads its newest row once at
   start, and applies a row only when it is newer than the one in force. A device
   that was offline gets the rows saved meanwhile as soon as it is back.
5. **Errors:** a device that cannot read its machine reports it with
   `report_error`; the board's toast shows it.

## Parameters, ports and tunnels

- `SAMPLE_INTERVAL` (`.ironflock/env-template.yml`): seconds between readings,
  per device, 1 to 60, default 5. The same default is in `main.py`.
- Port 8080 (`.ironflock/port-template.yml`, `UI_PORT` in `main.py`): the live
  view. A production install opens a remote-access tunnel for it; `main.py`
  writes the tunnel's URL into `devices.ui_url`, and the board embeds that URL
  on each device's page. A development run gets a private tunnel ending in
  `-dev`.

## Failure behaviour

- A table write waits up to the SDK's reconnect window for a restarting
  platform, then raises; the main loop catches it and tries again in the next
  round.
- The program stops cleanly on SIGTERM, so an update or a stop takes well under
  a second.
