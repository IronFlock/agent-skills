# How an IronFlock app is built

The rules and patterns for an app's architecture: what to ask before building
it, how its entities become tables and pages, where its state lives, how its
parts talk to each other, and what the platform does with its containers. The
starter app in `assets/app-template/` follows all of them; scaffold it with
`scripts/new_app.py <name>` (see SKILL.md) and adapt it.

## Contents

1. [The parts of an app](#the-parts-of-an-app)
2. [Rules](#rules)
3. [Understanding the app first](#understanding-the-app-first)
4. [The entities](#the-entities)
5. [Where each kind of data goes](#where-each-kind-of-data-goes)
6. [Reading and writing state with the SDK](#reading-and-writing-state-with-the-sdk)
7. [Entity tables: current state, updates and deletes](#entity-tables-current-state-updates-and-deletes)
8. [Following what the board writes](#following-what-the-board-writes)
9. [Commands, device functions and topics](#commands-device-functions-and-topics)
10. [The container on the device](#the-container-on-the-device)
11. [Docker Compose](#docker-compose)
12. [Web UIs on the device](#web-uis-on-the-device)
13. [Several devices](#several-devices)
14. [Checklist](#checklist)

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

1. **The entities come first.** What the app deals with, how each kind of thing
   is identified and how they relate decide the tables, the board's pages and
   the code. Settle that list before the first table (see
   [The entities](#the-entities)).
2. **The tables are the app's state.** Whatever the board, another device, a
   restarted container or an AI agent needs is in a table. A container keeps only
   what it can rebuild from the tables, such as an in-memory copy of its
   settings.
3. **The parts talk through the tables, not to each other.** A device writes
   what it measures and the state it is in, and the board shows it. The board
   writes what users decide, and the devices apply it. Neither calls the other,
   so the board works while devices are offline, and devices work while nobody
   has the board open. Device functions are for the few requests that need an
   answer from a device right now (see
   [Commands](#commands-device-functions-and-topics)).
4. **One writer per table.** Each table is written by the devices (each one about
   itself), by the board, or by one service. Say which in the table's
   `description`. Two writers of the same rows overwrite each other's changes.
5. **Desired state, not commands.** To change what devices do, write the target
   into a table (a limit, a setpoint, a recipe, a schedule) and let every device
   apply the newest row. A device that was offline applies it when it comes back,
   and applying it twice changes nothing.
6. **Write on change, follow live, never poll.** Write an entity's row when one
   of its values changes, and measurements at their sample rate. Readers follow
   the tables in realtime: the board's bindings, `subscribe_to_table` on a
   device, a websocket in a device's web UI. A timer that re-reads a table is
   always the wrong design.
7. **The board is the UI; a device's web UI adds to it.** Serve a web page from a
   device only for what a board cannot show: a machine's own HMI, video, a
   high-rate live view, an operator screen at the machine. The board embeds it.

## Understanding the app first

A new app, and a refactor that changes what an app is or does, start with a
short interview, before the first file. A wrong guess here costs the most to
undo, because everything below follows from the answers. Ask in one message,
only what the request leaves open, and wait:

- **How much does the user code?** Ask it plainly when the request does not
  show it: "Do you write code yourself, and in which language?" A developer
  gets the code, the design decisions and the trade-offs, in their language
  when the SDK has it (Python, JavaScript, Go). Someone who does not code gets
  a working app in Python, explanations in their own terms, and the steps to
  run it in IronFlock without touching a file; questions to them are about
  their work, never about tables or widgets.
- **What is the app for, and what does it give its users?** The goal in one
  sentence, and the value: what someone can see, decide or stop doing once the
  app runs. The board's home page answers that goal, and whatever does not
  serve it stays out of the first version.
- **What does the app deal with?** Its entities: the kinds of things it keeps
  track of, whether users create them or the devices find them. Ask for the
  list, how each one is identified (a name, a number, a serial, an address),
  and how they relate (an IPC has cameras, a camera has one stream). The next
  section turns the answer into tables and pages.
- **The follow-ups the answers call for**, as far as they still matter:
  - who uses the app, where and on what (an operator at a wall screen, a
    technician on a tablet, a manager at a desk), which is the board's brief
    in board-template.md;
  - where the data comes from: the machine, sensor or system, its protocol,
    the sample rate, what is read and what is computed;
  - what users set or change while the app runs, and what differs per device
    (a parameter) rather than per app (a settings table);
  - what the devices do on their own, and what waits for a user's decision;
  - what must be seen at a glance, what should raise an alarm, and how long
    data is kept;
  - whether a device serves a web page of its own, and who may open it;
  - what exists already: code, tables, a board, data that must survive.

Write the answers down where the next person finds them: the goal and the
value in README.md ("What it does"), the entities with their keys in CLAUDE.md
and in the `description` of data-template.yml. When the request already answers
the questions, state your understanding in a few lines (users, goal, entities
with their keys) and go on without waiting; the user corrects it at the
cheapest moment. A small change to an existing app needs no interview.

## The entities

An app is shaped by what it deals with. A camera app deals with IPCs, cameras,
streams, sources and AI models; a vehicle app with cars, drivers, routes and
drives; a maintenance app with machines, tasks and reports. That list, with
each entity's identifying key and the relations between them, is the app's
model. Every table, page and form, and most of the code, follow from it, so get
it right before anything else, and keep it in CLAUDE.md as a table:

| Entity | Key | Written by | On the board |
|---|---|---|---|
| IPC | `device_key` | the device, about itself | list, state |
| camera | `camera_id`, the name users give it | the board's forms | list, new, edit, delete |
| camera state | `camera_id` | the device | the state next to each camera |
| model | `model_id` | the board's forms | list, new, edit, delete |
| stream | `stream_id`, with `camera_id` and `model_id` | the board's forms | list per camera, new, edit, delete |
| detection | `stream_id` + `tsp` | the device | chart and table per stream |

**From the entities to the tables:**

- **One entity table per entity**, named after it in the plural (`cameras`,
  `streams`), with `maintainLatestFlagFor` on the column(s) that identify it.
  The key is something users or devices know: a name, a code, a serial number,
  a plate, an address, or `device_key` for an entity that is the device itself.
  There is no generated id. A "New" form asks for the key as a required field
  (with `validation` when it has a format), and a device writes the key it
  reads from the hardware.
- **Relations are key columns.** A child carries its parent's key (`streams`
  has `camera_id`), an assignment is a column on the entity that gets assigned
  to (`streams.model_id`), and a many-to-many is an entity of its own, keyed by
  both. A binding cannot join, so the board shows a relation by filtering the
  child's table on the parent's key from the route (pattern 2 in
  board-template.md), and a transform joins only for what a filter cannot show.
- **Readings and events carry the entity's key.** `detections` has `stream_id`
  and `tsp`, `drives` has `car_id` and `driver_id`. These tables have no
  `maintainLatestFlagFor`, because every row counts.
- **One writer per entity table**, as everywhere. An entity users create and
  change (a camera's name and address, a model) is written by the board's
  forms and has a `deleted` column. An entity the device finds or watches is
  written by the device, keyed the same way. When both sides have something to
  say about one entity, split it: a definition table the board writes
  (`cameras`) and a state table the device writes (`camera_status`, keyed by
  `camera_id`), shown side by side.
- **The entity at each device** (the machine the device is attached to) is keyed
  by `device_key` and written by the device about itself (see
  [Several devices](#several-devices)).

**From the entities to the board.** Every entity users manage gets the shape of
"Boards that manage assets" in board-template.md:

| Users want to | Widget | Bound to |
|---|---|---|
| see the entities | widget-table as the overview on the type's page, widget-sidenav as the way to each one | the entity table itself, with `{latest: true}` and the filter on `deleted` |
| create one | widget-form with `formButton: $bool:true`: a floating action button over the list that opens the form in a dialog | the entity table; the fields are the key and what a new entity needs |
| change one | widget-form on the entity's detail page (`/cameras/*`), prefilled from the record, the key a `hiddenField` filled from the route | the same table |
| delete one | that form's `deleteButton`, with `deleteFlagColumn` on `deleted` and `deleteNavigationRoute` back to the list | the same table |

Give the "New" form the same `deleteFlagColumn` as the edit form, so every row
carries the flag. The lists, and a detail page's view of one entity, are bound
to the raw entity table with the two filters and never to a transform: a
transform refreshes on its schedule tick, so the list would stop following a
save or a delete live (see
[Entity tables](#entity-tables-current-state-updates-and-deletes)). An entity
the devices write is listed the same way, without the forms. Readings and
events are not listed as entities but shown as charts and tables over a time
window, filtered by the entity's key.

## Where each kind of data goes

| Data | Where | Written by | Read by |
|---|---|---|---|
| Readings over time | a table with `tsp` | `publish_to_table`, `publish_rows_to_table` | charts with time windows and aggregation |
| The current state of a device, machine or order | an entity table (`maintainLatestFlagFor`) | a row with the key, `tsp` and the changed columns | the `{latest: true}` filter |
| Limits, setpoints, recipes people set for the app | a table the board's widget-form writes | the form | every device, as in [Following what the board writes](#following-what-the-board-writes) |
| Records people create, edit and delete | an entity table with a `deleted` column | the form, with `deleteFlagColumn` | the `{latest: true}` filter plus a filter on `deleted`, live; see [Entity tables](#entity-tables-current-state-updates-and-deletes) |
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
| Follow | `subscribe_to_table(table, handler)` | Every new row, as the platform stores it, also across reconnects |
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
  `deleteFlagColumn`). Old rows age out with the table's `dropAfter`. The next
  section has the rules.
- **The SDK hides the connection.** The program calls everything on its
  `IronFlock` object and never deals with sessions: the SDK reconnects, restores
  subscriptions and device functions, and delivers to a table subscription the
  rows stored while the connection was down (`ironflock` 1.10.0 and later).
  Never reach into `flock.connection`.
- **Append what must not be lost.** `append_to_table` waits up to a minute
  (`reconnect_window`) for a restarting platform, the router and the data
  backend alike, and raises `RuntimeError` when it does not come back.
  `publish_to_table` waits only for the connection: a row published while the
  data backend restarts is acknowledged and lost. Append state changes and
  records; publish high-rate readings. Catch `RuntimeError` in a loop that must
  keep running, and buffer the rows if none may be lost.
- **A table's columns are its contract.** A key the code writes that no column
  declares is dropped, and a column nobody writes stays empty; neither raises.
  Keep data-template.yml and the code in step.

## Entity tables: current state, updates and deletes

An entity table (`maintainLatestFlagFor`) is the history of its entities: every
change is a new row with the key, a `tsp` and the changed columns. The platform
never edits or deletes a row, and nothing has to, because the readers pick the
current state at read time:

- **Current state is a read mode, not a view.** The `{latest: true}` filter
  returns the newest row per entity key, chosen by `tsp` when the read runs.
  Board bindings and `getHistory` take it alike. The table keeps every version;
  the filter shows one per entity.
- **It is live.** A widget bound to the table with `{latest: true}` gets every
  new row in realtime, in under a second, and replaces the entity's row with
  it. The old version disappears from the widget the moment the new one arrives.
  Nothing has to be refreshed, recomputed or scheduled.
- **A delete is a column.** Give the table a boolean `deleted` column. Deleting
  writes a row with `deleted: true` (the board's form does this through
  `deleteFlagColumn`), and saving the record again writes `deleted: false`,
  which restores it. Readers filter on the column (the OR group in
  board-template.md, "Filters", which also lets users show deleted records).
  The latest filter picks the newest row per entity first and applies the
  other conditions afterwards, so an entity whose newest row is deleted drops
  out of the widget as soon as that row arrives, and an older, undeleted row
  never takes its place.
- **Never build a transform for this.** A view that deduplicates an entity table
  by key or hides its deleted rows reproduces what the two filters do, but a
  transform reaches the board only on its `schedule` tick, so every change
  shows up seconds or minutes late. Transforms are for what a binding cannot
  compute: joins, arithmetic, aggregations over current rows. When such a
  transform needs the current state of entities, select it in its SQL with
  `DISTINCT ON (<key>) ... ORDER BY <key>, tsp DESC` and filter `deleted` there.
- **Code reads it the same way.** `getHistory(table, {"limit": 500, "filterAnd":
  [{"latest": True}, {"column": "deleted", "operator": "=", "value": False,
  "dataType": "boolean"}]})` gives the current, undeleted entities; `subscribe_to_table` delivers each new
  row, and a program applies it to its copy of the entity, or drops the entity
  when the row says `deleted`.

## Following what the board writes

A device that applies board-written state, such as a limit set on the board,
follows the table in three steps. The starter's `main.py` does all three:

1. **Subscribe first** with `subscribe_to_table`, so no row falls between the
   read and the subscription.
2. **Read the newest row** with `getHistory` and `{"latest": True}`, and apply it.
3. **Apply a row only if it is newer** (`tsp`) than the one in force. A row saved
   just as the program starts can arrive from the read and from the
   subscription.

Reconnects need nothing more. The router does not replay what was published
while a device was offline, so the SDK does it: after every reconnect, the
subscription's handler first gets the rows stored meanwhile, oldest first, and
then the rows that arrive live. A limit saved while a device was offline reaches
it as soon as it is back. The catch-up goes by `tsp`: it delivers the rows newer
than the newest one the handler got, at most 10000. Its read waits for the data
backend like any history read, up to the reconnect window, and when it fails,
those rows are not delivered and only a warning is logged. It came with
`ironflock` 1.10.0; with an older SDK such a row is lost until the next change or
restart.

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
(an entity table keyed by the id, written by the device), so a command it gets
twice, from the read at start and from the subscription, runs once.

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
  is `DEV`): it writes to the app's development tables and gets default
  parameters. Each http(s) port gets a private tunnel that only users with the
  Develop privilege on the device open, from the IDE's side menu. Each tcp/udp
  port gets a tunnel with no login, whose address `getRemoteAccessUrlForPort`
  returns once it is up. Those users can switch each port's tunnel off.
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
   `device_key`, at start. A development run writes no URL: the SDK gives it the
   production install's, and its own tunnel is opened from the IDE's side menu.
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

1. The entity model is written down in CLAUDE.md: each entity has its own
   entity table, keyed by what identifies it, relations and readings carry
   those keys, and every entity users manage has a list, a "New" form in a
   dialog, and a detail page with edit and delete on the board, bound to the
   table itself.
2. All state is in tables, each with one writer named in its description, and
   every column the code writes is declared in data-template.yml.
3. Every row has a `tsp`; state rows are written on change and hold only the key
   and the changed columns. Entity tables are read with `{latest: true}` and a
   filter on `deleted`, never through a transform that deduplicates or cleans
   them.
4. Board-written state is followed in the three steps above, with `ironflock`
   1.10.0 or later; the code never touches `flock.connection`, and `main()` never
   returns.
5. Table writes in long-running loops catch `RuntimeError`; expected failures
   are handled in the program and reported with `report_error` and a
   `user_message`.
6. The program exits on SIGTERM, starts in exec form and logs unbuffered.
7. Nothing polls: the board binds, devices subscribe, web UIs push.
8. Each served port is declared in port-template.yml, its URL comes from
   `getRemoteAccessUrlForPort` and is written to a table, and the board embeds it
   from there.
9. A Compose app follows the rules above: no `env_file:`, no `profiles:`, no
   `${VAR}` host ports, named volumes for files, and only the ports users need
   published.
10. `scripts/validate.py <app-dir>` reports no errors.
