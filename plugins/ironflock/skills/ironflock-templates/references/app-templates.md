# data, env, port and ai templates

Each of these files has a JSON Schema in `schemas/<name>/v1.yml` (in this skill's
folder) with a description on every field. Read the schema before writing the file;
this page only adds what a schema cannot say: how the file connects to the app's
code and to the rest of the platform.

Start every file with its schema line. It gives the developer validation and
autocomplete in their editor:

```yaml
# yaml-language-server: $schema=https://ironflock.com/schemas/data-template/v1.yml
```

## Contents

- [data-template.yml](#data-templateyml): tables in the project database
- [env-template.yml](#env-templateyml): app parameters
- [port-template.yml](#port-templateyml): remote access
- [ai-template.yml](#ai-templateyml): AI agents
- [The SDK](#the-sdk)

## data-template.yml

Docs: <https://ironflock.com/docs/app-development/data-backend>

When the app is installed in a project, the platform creates these tables in that
project's own database. Boards, the SQL workbench, AI agents and other apps then
read them.

- **The app fills the tables; the template only declares them.** Rows arrive through
  the SDK: `await flock.publish_to_table("sensordata", {"temperature": 21.5, ...})`.
  `tablename` must match the first argument, and each column's `path` (default
  `args[0].<id>`) picks the value out of the published object. Read the app's code
  and keep the two in agreement. A key the code publishes with no matching column is
  dropped, and a column nobody publishes stays NULL. Neither raises an error.
- **Every table has a `tsp` column of `dataType: timestamp`.** A published row
  without a value at the `tsp` path is rejected and logged as an error for the app.
  Boards order by `tsp`, and time windows and aggregation key on it. Publish an ISO
  8601 timestamp with a time zone.
- **Every column needs `id`, `name`, `description` and `dataType`.** The schema
  requires all four. Some older documentation examples omit `name` or `description`;
  follow the schema. Descriptions are read by people in the board editor and by AI
  agents, so say what the value means and its unit.
- **Give every table one writer, and name it in the table's `description`**: each
  device about itself, the board's form, or one service. app-architecture.md
  explains why, and how a device follows a table the board writes.
- **`device_key` and `authid` exist on every table automatically**, so don't declare
  them (the schema reserves those ids). `device_key` identifies the device that
  published the row, which makes it the natural pivot for "one series per device" and
  the usual entity key: `maintainLatestFlagFor: [device_key]`.
- `maintainLatestFlagFor` makes a table an entity table: the newest row per entity
  (by `tsp`) is the entity's current state. To change an entity, send a new row with
  the key, a `tsp` and only the changed columns. A column the row omits is inherited
  from the previous row, and an explicit `null` clears it. Use it for state such as
  machine status, settings or orders. Read the current state with the
  `{latest: true}` filter (see board-template.md); there is no `latest_flag` column.
- Transforms are SQL views over the app's own tables. Boards can bind to them, but
  board-side aggregation only works on plain tables. Do the aggregation in the
  transform's SQL instead.
- **A transform's `sql` can be any single SQL `SELECT` statement**, with PostgreSQL
  and TimescaleDB semantics. That includes CTEs (`WITH ... SELECT`). When a
  computation needs intermediate steps, put them in CTEs of one transform rather
  than chaining several transforms.
- **A transform reaches open boards only on its `schedule` tick**, not when a table
  underneath changes. With `* * * * *` a new record shows up in a transform-driven
  menu or list up to a minute late. Give the views behind menus, lists and live
  states a seconds tick: a sixth, leading field is seconds (`*/5 * * * * *`).
- **Mark app-internal tables and transforms `private: true`.** Decide this for
  every table. Users of the app should see only data that means something to them:
  values they analyze, chart, alarm on or build dashboards with. Internal details
  are different. Examples are job queues, sync cursors, retry and connection state,
  raw protocol frames, calibration internals, debug output and staging rows that a
  transform cleans up. Ask: would a user of this app want to chart this, filter by
  it or set an alarm on it? If not, or if it would confuse them more than it helps,
  make it private. If they would, leave the default (`false`, shared).
  - No user can reach a private table directly. It isn't offered for their own
    dashboards or alarms, the SQL workbench, data export or AI agents, and other
    apps can't read it, not even through `consumes`.
  - Only the app itself uses it: its code, its transforms and its board. Users see
    whatever those show, so that part is your responsibility. A shared transform
    over a private table, or a board widget bound to one, should show only what
    users should see.
  - A board widget bound to a private table opens all of that table's rows to
    everyone who can open the board, not only the part the widget shows. If the
    board needs only part of the table, add a private transform that holds just
    that part, and bind the widget to the transform.
- Add `downsample` to tables that will back charts spanning weeks or months.
- To read another app's tables, list it under `consumes:`. Board widgets that bind
  to those tables then need `provider_app` on their data reference (see
  board-template.md).

## env-template.yml

Docs: <https://ironflock.com/docs/app-development/app-parameters>

Parameters the user can set per device or per device group without a custom UI.

- Top-level keys are environment variable names (`^[A-Z0-9_]+$`). Each holds
  `label` and `type` (`numeric`, `text`, `textarea` or `boolean`) plus optional
  `defaultValue`, `description`, `unit`, `min`, `max`, `secret` and `valueList`.
- **A dropdown is `valueList: [a, b, c]`.** An older documentation example shows
  `type: select`, `options` and `optional`. The schema rejects `type: select`, and
  the parameters form ignores `options` and `optional`, so don't use any of them.
- Values reach the container as environment variables, so they are always strings.
  Parse them in code, and fall back to the same default as `defaultValue`. Every
  value is also written to `/data/env/<NAME>.txt`, and a value over 20 KB exists
  only there.
- `defaultValue` is what the app gets while running in development.
- The platform always sets `DEVICE_KEY`, `DEVICE_NAME`, `DEVICE_SERIAL_NUMBER`,
  `SWARM_KEY`, `APP_KEY`, `APP_NAME`, `ENV` and the other variables listed in
  app-architecture.md ("The container on the device"). Don't declare them, and
  give parameters specific names (`PLC_HOST`, not `HOST`) that no other variable's
  name or value contains.
- Parameters belong to one device or device group. Settings that users change
  while the app runs, or that apply to many devices, belong in a table the board
  writes (app-architecture.md, "Parameters or a settings table?").

## port-template.yml

Docs: <https://ironflock.com/docs/remote-access/port-template>

Ports the app serves (a web UI, a video stream, VNC, an OPC UA server), offered
as remote-access tunnels. A production install switches every declared port's
tunnel on; users with the network privilege on the device can switch it off. An
`http` tunnel stays private (IronFlock login or account API key) unless the port
is switched Public; a `tcp`/`udp` tunnel is a raw port with no login in front, so
the app must authenticate its clients itself.

- `ports: [{name, port, main?, protocol?, remote_port_environment?}]`. `port` is the
  port the app listens on. `protocol` defaults to `http`, which is served to the
  user as HTTPS with websockets working. Use `tcp` or `udp` for raw sockets.
- Mark at most one port `main: true`. It is opened when the user clicks the app's
  icon on a device.
- Several apps can run on one device, so the platform maps each declared port to a
  free host port. The app learns the real values from injected variables:
  `DEVICE_LAN_IP`, `DEVICE_PORT_FOR_<port>`, and for an active tcp/udp tunnel
  `REMOTE_PORT_FOR_<port>`. Never hard-code the declared port into a URL you show
  to the user.
- **To show a device's web UI on the board**, the app writes the URL from
  `getRemoteAccessUrlForPort(<port>)` into the device's row of a table, and the
  board's widget-embed binds `webUrl` to that column. Tunnels exist for production
  installs only. app-architecture.md ("Web UIs on the device") has the whole
  pattern, and board-template.md the binding.

## ai-template.yml

Docs: <https://ironflock.com/docs/app-development/ai-template>

AI agents the app contributes to the IronFlock assistant.

- Top-level keys are agent names. Exactly one agent should be `main: true`. That is
  the one the IronFlock assistant can call, and its `tool_description` tells the
  assistant when to call it. The others are sub-agents, reached through a
  `delegate:` tool.
- Required on every agent: `system_prompt`, `tools` (at least one),
  `max_context_tokens`, `messages_after_summary` and `max_iterations`.
- Each tool has a `description` and exactly one of `topic` or `delegate`.
- A tool with `topic: <name>` calls a function the app registers on each device:
  `await flock.register_device_function("<name>", handler)`. The names must match
  exactly. The platform adds a required `device_key` parameter so the assistant can
  pick the device, and strips it before the call, so don't declare it and don't
  expect it in the handler. The handler's return value and error messages go
  straight to the model, so make them readable text or small JSON.
- `register_function()` still works but is deprecated. Write
  `register_device_function()` in new code.
- `data_access: true` gives the agent read-only SQL over the app's own tables.
  The agent learns the columns from data-template.yml descriptions, so write those
  well instead of repeating them in `system_prompt`. Its SQL can't reach private
  tables and transforms, like any agent's. If it needs part of one, add a shared
  transform with that part. Its `topic:` tools run in the app's own code, which
  reads private tables normally.

## The SDK

The code reads and writes the tables, follows them and registers device functions
through the `ironflock` SDK (`pip install ironflock`, `npm install ironflock`, or
`github.com/ironflock/sdk-go`). app-architecture.md ("Reading and writing state
with the SDK") lists the calls and what they guarantee, and the starter app's
`main.py` uses them. One rule is easy to miss: `main()` must not return, because
the SDK closes the connection when it does, and with it every registered device
function and subscription.
