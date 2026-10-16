# How an IronFlock app is built

The rules and patterns for an app's architecture: where its state lives, how its
parts talk to each other, and what the platform does with its containers. The
starter app in `assets/app-template/` follows all of them; scaffold it with
`scripts/new_app.py <name>` (see SKILL.md) and adapt it.

## Contents

1. [The parts of an app](#the-parts-of-an-app)
2. [Rules](#rules)
3. [Where each kind of data goes](#where-each-kind-of-data-goes)
4. [Reading and writing state with the SDK](#reading-and-writing-state-with-the-sdk)
5. [Following what the board writes](#following-what-the-board-writes)
6. [Commands, device functions and topics](#commands-device-functions-and-topics)
7. [The container on the device](#the-container-on-the-device)
8. [Docker Compose](#docker-compose)
9. [Web UIs on the device](#web-uis-on-the-device)
10. [Several devices](#several-devices)
11. [Checklist](#checklist)

## The parts of an app

An app runs on many devices at once, typically industrial PCs next to machines:

```text
 device 1 ┐                                               ┌─ board: the app's UI, in IronFlock
 device 2 ├─ container(s) ── SDK ── app realm ── tables ──┼─ alarms, AI agents
 device n ┘       │                                       └─ other apps (read only)
                  └─ web UI on a port ── remote-access tunnel ── browser, board embed
```

| Part | What it is | Declared in |
|---|---|---|
| Edge program | One container, or a Compose stack, on every device the app is installed on | `Dockerfile` or `docker-compose.yml` |
| SDK | The program's only link to the platform: tables, realtime feeds, device functions, files | the `ironflock` package (Python, JavaScript, Go) |
| Tables | The app's state, in the project's own database | `.ironflock/data-template.yml` |
| Board | The app's central UI: widgets bound live to the tables, for all devices | `.ironflock/board-template.yml` |
| Parameters | Settings of one device or device group, made in its app settings | `.ironflock/env-template.yml` |
| Remote access | Tunnels to ports the containers serve, such as a web UI | `.ironflock/port-template.yml` |
| AI agents | Agents for the IronFlock assistant, with device functions as tools | `.ironflock/ai-template.yml` |

Installing the app in a project creates its tables in that project's database,
installs its board, and opens a private messaging realm (WAMP, realtime pub/sub)
that connects the app's containers on all devices, its tables and its board. The
SDK joins that realm with the identity the device agent injects, so the code
needs no address and no credentials.

## Rules

1. **The tables are the app's state.** Whatever the board, another device, a
   restarted container or an AI agent needs is in a table. A container keeps only
   what it can rebuild from the tables, such as an in-memory copy of its
   settings.
2. **The parts talk through the tables, not to each other.** A device writes
   what it measures and the state it is in, and the board shows it. The board
   writes what users decide, and the devices apply it. Neither calls the other,
   so the board works while devices are offline, and devices work while nobody
   has the board open. Device functions are for the few requests that need an
   answer from a device right now (see
   [Commands](#commands-device-functions-and-topics)).
3. **One writer per table.** Each table is written by the devices (each one about
   itself), by the board, or by one service. Say which in the table's
   `description`. Two writers of the same rows overwrite each other's changes.
4. **Desired state, not commands.** To change what devices do, write the target
   into a table (a limit, a setpoint, a recipe, a schedule) and let every device
   apply the newest row. A device that was offline applies it when it comes back,
   and applying it twice changes nothing.
5. **Write on change, follow live, never poll.** Write an entity's row when one
   of its values changes, and measurements at their sample rate. Readers follow
   the tables in realtime: the board's bindings, `subscribe_to_table` on a
   device, a websocket in a device's web UI. A timer that re-reads a table is
   always the wrong design.
6. **The board is the UI; a device's web UI adds to it.** Serve a web page from a
   device only for what a board cannot show: a machine's own HMI, video, a
   high-rate live view, an operator screen at the machine. The board embeds it.

## Where each kind of data goes

| Data | Where | Written by | Read by |
|---|---|---|---|
| Readings over time | a table with `tsp` | `publish_to_table`, `publish_rows_to_table` | charts with time windows and aggregation |
| The current state of a device, machine or order | an entity table (`maintainLatestFlagFor`) | a row with the key, `tsp` and the changed columns | the `{latest: true}` filter |
| Limits, setpoints, recipes people set for the app | a table the board's widget-form writes | the form | every device, as in [Following what the board writes](#following-what-the-board-writes) |
| Records people create, edit and delete | an entity table with a `deleted` column | the form, with `deleteFlagColumn` | board-template.md, pattern 6 |
| Errors and notices for operators | the `error-logs` table | `report_error(error, user_message=...)` | widget-toast |
| Images, documents, recordings | the app's file storage (`flock.files`) | `files.put` | the file's URL in a column, shown by a widget |
| Passwords, API keys | a `secret: true` column | any table write | `reveal_secrets`, `verify_secret`, in the app's own containers only |
| One device's installation: a machine's address, a serial port | `env-template.yml` | the device's or group's app settings | the environment |
| Messages between parts that nobody needs later | the app's own topics | `publish` | `subscribe` |
| A request that needs one device's answer now | a device function | `register_device_function` | `call_device_function`, widget actions, AI tools |

**Parameters or a settings table?** Parameters belong to a device or a device
group: whoever installs or configures it sets them in IronFlock's app settings,
and the program reads them from its environment. Use them for what differs per
installation. What users change while the app runs (limits, recipes, schedules,
anything that applies to many devices) belongs in a table the board writes: the
board is where users work with the app, every device follows a change at once,
and the table keeps the history of who changed what and when (`authid`, `tsp`)
for the board, alarms and AI agents.

## Reading and writing state with the SDK

Install `ironflock` from PyPI or npm, or `github.com/ironflock/sdk-go`. The three
SDKs have the same functions; Python names are used here. JavaScript uses
camelCase (`publishToTable`), Go capitalises (`PublishToTable`) and takes a
`context.Context` first.

```python
from ironflock import IronFlock

async def main():
    ...  # runs once the connection is up; it must not return

if __name__ == "__main__":
    flock = IronFlock(mainFunc=main)
    flock.run()
```

`run()` connects and then calls `main()`. When `main()` returns, the SDK closes
the connection, so a program that runs until it is stopped never returns from
`main()`.

| Operation | Python | What it does |
|---|---|---|
| Create, update | `publish_to_table(table, row)` | Writes a row; fire and forget |
| Create, update, with the outcome | `append_to_table(table, row)` | Writes a row; a refused row raises |
| Many rows at once | `publish_rows_to_table`, `append_rows_to_table` | One message, all or nothing |
| Read | `getHistory(table, {"limit": n, ...})` | The newest matching rows, oldest first |
| Read the current state | `getHistory(table, {"limit": n, "filterAnd": [{"latest": True}]})` | The newest row per entity |
| Read aggregated | `get_series_history(table, params)` | One row per time bucket |
| Follow | `subscribe_to_table(table, handler)` | Every new row, as the platform stores it |
| Report an error | `report_error(error, user_message=...)` | A row in `error-logs`, shown by widget-toast |
| Delete | a row with `deleted: True` | Rows are history; see below |

- **Every row needs a `tsp`**, an ISO 8601 timestamp with a time zone. A row
  without one is dropped, and only the app's `error-logs` table says so.
- **Every write carries the device's key and name.** The platform stores the key
  in `device_key`. A column with `path: kwargs.DEVICE_NAME` stores the device's
  name with no code at all. Rows the board writes have no device.
- **Reads return timestamps as epoch milliseconds** and numeric columns as
  numbers, from `getHistory` and in realtime events alike.
- **Update an entity with a partial row**: its key, a `tsp` and the columns that
  change. A column the row leaves out keeps its value; `None` clears it.
- **There is no delete.** Retire an entity by writing `deleted: True` and filter
  it out where it is read (board forms write the flag through
  `deleteFlagColumn`). Old rows age out with the table's `dropAfter`.
- **Writes ride out a platform restart.** A table write waits up to a minute
  (`reconnect_window`) for the connection to come back, then raises
  `RuntimeError`. Catch it in a loop that must keep running, and buffer the rows
  if none may be lost.
- **A table's columns are its contract.** A key the code writes that no column
  declares is dropped, and a column nobody writes stays empty; neither raises.
  Keep data-template.yml and the code in step.

## Following what the board writes

A device that applies board-written state, such as a limit set on the board,
follows the table in four steps. The starter's `main.py` does all four:

1. **Subscribe first** with `subscribe_to_table`, so no row falls between the
   read and the subscription.
2. **Read the newest row** with `getHistory` and `{"latest": True}`, and apply it.
3. **Read again after every reconnect.** The SDK restores subscriptions after a
   reconnect, but rows written in the meantime are not replayed: a limit saved
   while a device was offline never reaches its subscription. The SDKs have no
   public join callback yet. In Python, listen to the join event of the
   connection's autobahn component:
   `flock.connection.component.on("join", handler)`, where `handler(session,
   details)` is a coroutine that reads the table again.
4. **Apply a row only if it is newer** (`tsp`) than the one in force. Rows from
   the read, the subscription and the re-read arrive in no guaranteed order.

```python
await flock.subscribe_to_table("settings", lambda row, *a, **kw: apply(row))
for row in await flock.getHistory("settings", {"limit": 1, "filterAnd": [{"latest": True}]}) or []:
    apply(row)
```

A table without an entity key holds one setting for all devices: the newest row
is in force. For settings per device or per machine, key the table by the target
(see [Several devices](#several-devices)).

## Commands, device functions and topics

**Prefer state.** Most things users "command" are desired state: a setpoint, on
or off, a recipe. Write them into a table, as above.

**Commands that must run once** (print a label, start a cleaning cycle) are rows
with an id in a table the board writes. The device records the ids it has done
(an entity table keyed by the id, written by the device), so the re-read after a
reconnect skips them.

**Device functions** are procedures a device registers:
`await flock.register_device_function("set_lamp", handler)`. Use them when the
caller needs the device's answer now:

- AI agents: a tool with `topic: <name>` in ai-template.yml calls the function on
  the device the assistant picks (see app-templates.md).
- widget-switch and widget-scada actions. The board editor sets the app and
  device they call, and they work only while the device is online.
- Calls between your own containers or devices:
  `await flock.call_device_function(device_key, "name", args=[...])`.

The handler's return value goes to the caller, so return readable text or small
JSON, and return an expected failure (a machine that is off) as a result rather
than raising it. Register only through `register_device_function`; the platform
refuses other registrations.

**Topics** carry messages that nobody needs later, between your own parts:
`publish("myapp.events", ...)` and `subscribe("myapp.events", handler)`. Pick
names in your own namespace. Names that start with a digit, `sys.`, `wamp.`,
`bulk.`, `transformed.`, `databackend.errors.`, `files.`, `append.`,
`appendBulk.`, `history.` or `secret.` belong to the platform. The board cannot
subscribe to topics: whatever it shows must be in a table.

## The container on the device

What the device agent gives a container and expects from it:

- **Identity.** The agent sets `DEVICE_KEY`, `DEVICE_NAME`,
  `DEVICE_SERIAL_NUMBER`, `SWARM_KEY`, `APP_KEY`, `APP_NAME`, `ENV` (`DEV` or
  `PROD`), `TUNNEL_DOMAIN`, `DEVICE_LAN_IP` and `DEVICE_PORT_FOR_<port>`, and the
  app's own credential for the SDK. It keeps current copies under `/data/env`,
  which only root can read. The SDK reads all it needs; never hard-code any of
  them.
- **Parameters.** A production install gets the values users set, and the
  template's `defaultValue` for the rest. A development run gets only the
  defaults.
- **Files.** A single-image app gets `/data`, private to the app and kept across
  restarts and updates (deleted with the app), and `/shared`, shared by all apps
  on the device. Keep the app's state in tables anyway, and use these for files
  that belong to the device, such as a downloaded model or a cache.
- **Hardware.** A single-image container runs privileged, with the device's
  `/dev`, on Docker's bridge network.
- **Logs.** Everything the program writes to stdout and stderr is the app's log
  in IronFlock. Write it unbuffered (`python -u`).
- **Start.** The container must be running 30 seconds after it starts, or the
  start counts as failed.
- **Crashes.** When a production app exits, the agent starts it again, waiting
  longer after each failure. A development run is not restarted. So handle
  expected failures (a sensor that does not answer, a lost connection) in the
  program, and let it exit on errors it cannot recover from.
- **Stop.** The program is the container's PID 1, which ignores SIGTERM unless it
  handles the signal. Exit on SIGTERM, or stopping the app waits until Docker
  kills it. Start it in exec form (`CMD ["python", "-u", "main.py"]`), never
  through a shell.
- **Development runs.** Running the app from the IDE is a development run (`ENV`
  is `DEV`): it writes to the app's development tables, gets default parameters
  and no remote-access tunnels.
- **Architectures.** Devices are arm64, amd64 or armv7. A `Dockerfile.<arch>`
  next to the `Dockerfile` overrides it for one architecture.

## Docker Compose

Use a `docker-compose.yml` when the app runs several processes, or bundles
third-party services (an MQTT broker, a database, a vendor's server) next to its
own code. It sits at the repository root. The whole stack starts and stops as
one app. What changes compared with a single image:

- **Every service gets the injected environment.** The agent gives each service
  its own `env_file` with the variables above: an `env_file:` you write is
  replaced, and a `${VAR}` in the file resolves against the injected values.
- **No `/data`.** Services get only `/data/env`, read-only. Keep files in named
  volumes: they survive stops and updates and are deleted when the app is
  removed from the device.
- **Published ports are remapped.** Each `ports:` entry with a host port gets a
  free host port on all interfaces (a host IP such as `127.0.0.1` is dropped),
  and `DEVICE_PORT_FOR_<port>` gives the real one. The port-template refers to
  the host port as written in the file. Publish only what users should reach,
  and let services talk to each other over the Compose network by service name.
  A `${VAR}` host port is not managed: it gets no remapping and no tunnel.
- **Nothing is added.** The agent grants Compose services no privileges and no
  devices. Declare `privileged`, `devices` or `device_cgroup_rules` yourself. A
  `devices:` entry names hardware that must exist, or the container does not
  start; `device_cgroup_rules` with a `/dev` volume works on every device.
- **No `profiles:`.** A service with profiles is left out of the release.
- **The same start rule.** Within 30 seconds every container must be running or
  have exited with code 0, and at least one must be running. Give long-running
  services `restart: unless-stopped`.
- **Each of your services is a part of the app.** A service of your own that
  talks to the platform has its own SDK session, and reaches the app's other
  services through the tables, device functions or topics, like any other part.

## Web UIs on the device

A web server in the container becomes reachable from anywhere through the
remote-access tunnel of its port:

1. **Serve on a fixed port** (bind `0.0.0.0`) and declare it in
   port-template.yml with `protocol: http`. A production install switches the
   tunnel on, and serves it as HTTPS with websockets.
2. **Write its URL into a table.** `getRemoteAccessUrlForPort(port)` gives the
   tunnel's URL. Write it into the device's row of an entity table keyed by
   `device_key`, at start. Only production installs get tunnels: a development
   run writes no URL (the SDK would give it the production install's).
3. **Embed it in the board.** Bind widget-embed's `webUrl` to that column,
   filtered to one device (board-template.md, "Embedding a web UI the app
   serves").

Rules for the page:

- **Who can open it.** An http tunnel is private: only people who are signed in to
  IronFlock and have access to the device open it, unless a user switches the port
  to Public. On the device's network it is open to everyone at
  `http://DEVICE_LAN_IP:DEVICE_PORT_FOR_<port>`. Show nothing there that the
  plant's network may not see, and require a login of your own for anything that
  changes state.
- **Relative URLs.** Load assets, call the API and open the websocket relative to
  the page, so it works on the device's network, through the tunnel and behind a
  reverse proxy path.
- **Push, never poll.** Send updates over a websocket; the tunnel carries it.
- **No platform credentials in the browser.** The page talks to its own server,
  and the server holds the SDK session.
- **A machine's own HMI.** To show the web HMI a machine serves on the plant
  network, reverse-proxy it from a container on a declared port (see the
  IronFlock docs, "Embedding external HMIs").

## Several devices

- **Every row carries its device**: `device_key` is set on every row a device
  writes. Key per-device entity tables by `device_key`, store the name with
  `path: kwargs.DEVICE_NAME`, and pivot charts by the name.
- **A device list and a page per device**: a data-driven menu over the device
  table with `route: device_key`, and on the `*` page a filter
  `{column: device_key, operator: '=', value: '2', dataType: numeric, useRoute: true}`
  (board-template.md, pattern 2). The starter's board does this.
- **Settings per device or per machine**: key the settings table by a column
  that names the target (the board's rows have no `device_key`), and fill it in
  the form from the page's route, as a hidden field. Each device applies the
  newest row for its own key.
- **A device that leaves** keeps its rows. If users must be able to remove it
  from the lists, give the device table a `deleted` column and the board a form
  that sets it.

## Checklist

1. All state is in tables, each with one writer named in its description, and
   every column the code writes is declared in data-template.yml.
2. Every row has a `tsp`; state rows are written on change and hold only the key
   and the changed columns.
3. Board-written state is followed in the four steps above, and `main()` never
   returns.
4. Table writes in long-running loops catch `RuntimeError`; expected failures
   are handled in the program and reported with `report_error` and a
   `user_message`.
5. The program exits on SIGTERM, starts in exec form and logs unbuffered.
6. Nothing polls: the board binds, devices subscribe, web UIs push.
7. Each served port is declared in port-template.yml, its URL comes from
   `getRemoteAccessUrlForPort` and is written to a table, and the board embeds it
   from there.
8. A Compose app follows the rules above: no `env_file:`, no `profiles:`, no
   `${VAR}` host ports, named volumes for files, and only the ports users need
   published.
9. `scripts/validate.py <app-dir>` reports no errors.
