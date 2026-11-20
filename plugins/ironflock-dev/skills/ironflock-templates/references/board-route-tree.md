# The route tree

This reference covers how to decide a board's pages before any widget is
placed: the route tree, how routes follow the entities the board shows, and how
menus and tab bars build their links along it. It applies to every board with
more than one page. What each page shows and how it looks is in
board-design.md; the standard shape of the lists, forms and detail pages of
assets users manage is in board-assets.md.

## Decide the pages first

Decide the board's pages before you place the first widget. The entity model
gives the tree its shape: which entities users open, and which one belongs to
which. In the data, an entity type is an entity table, a table with an entity
key (`maintainLatestFlagFor`) whose newest row per key is the entity's current
state, and a column that holds another entity's key is a relation (a stream's
`device_id`: the stream runs on that device). The board's brief decides the
rest: what the home page answers, what each page shows, who needs which page,
and where the actions go.

Write the tree down, one line per route with the page's name, what it shows
and its main action, before the first widget. Then build the pages one by one,
each answering its line. A board about a single subject can be one page.

## The rules

1. **Home answers the app's goal.** `/` is not a list of entities. It is the
   summary the brief asks for (what runs, what needs attention, the latest
   events, the figures that matter), and its tiles lead to the entities'
   pages.
2. **An entity users open gets a type segment and a key segment.** `/stream`
   lists the streams, `/stream/<stream>` is one stream. Name the type segment
   after the entity, in the same form on every level (`/stream` and
   `/stream/<stream>/zone`, or `/streams` and `/streams/<stream>/zones`,
   never a mix of singular and plural). The key segment is the entity's id
   (`stream_id`), never its name: a name changes and need not be unique, so a
   route built from it breaks when the asset is renamed. Menus, titles and
   breadcrumbs show the name.
3. **A child's routes continue below its parent's key**, along the relations
   of the entity model (except below a device, rule 6). A zone is drawn on a
   stream, so a zone is `/stream/<stream>/zone/<zone>`. Each entity's table
   carries the keys of all entities above it (`zones` has `stream_id` and
   `zone_id`), so every row holds its full route. A URL then reads as a path
   of typed keys, and each prefix of it is a page of its own: the type segment
   below a key (`/stream/<stream>/zone`) is that parent's list of those
   children, with its "New" button. The key of the n-th level is always
   segment 2n, the number its `useRoute` filters take (stream `'2'`, zone
   `'4'`). Never put two keys in a row (`/streams/*/*`): nobody can tell which
   segment is which, and the first key gets a page that is not the page of
   the entity it names.
4. **Each entity has one page, where it sits in the tree.** Every link to a
   stream, from home, from a list, from an event or from its device's page,
   opens `/stream/<stream>`. No second route shows the same entity's page.
5. **An entity that belongs to no other entity is a root**, even when many
   others use it. A model that streams run gets its own branch (`/model`,
   `/model/<model>`). The relation shows on both sides: the stream's page names
   its model, and the model's page shows where it is used, such as whether it
   is ready on each device.
6. **The project's devices get a branch of their own, and what belongs to a
   device starts its own branch.** Many apps have a table of the IronFlock
   devices (the IPCs) in the project, usually `devices` or `gateways`, and
   most of their other entities belong to a device: a stream runs on a device,
   a connection is configured on a gateway. Yet the device is a technical
   detail, not what users come for, so it does not head the tree. It gets its
   own branch at the top (`/device`, `/device/<device>`) with its state, its
   technical details and "Remove device", and each entity that belongs to a
   device starts its own branch at the top instead of continuing below the
   device's key: `/stream/<stream>/zone/<zone>`, never
   `/device/<device>/stream/<stream>/zone/<zone>`. The relation shows on both
   sides, as for a root: the table keeps the device's key as a column
   (`streams.device_id`), the stream's page names its device and links to it,
   and the device's page lists the streams that run on it, each opening
   `/stream/<stream>`. The key segment must then identify the entity on its
   own: a generated id or a serial number does, a bus address or a channel
   number that repeats on every device does not, so the device writes a key
   that includes its own (`<device_id>-<address>`). An app without such a
   table, or whose entities do not belong to a device, skips this rule.
7. **A nested type that users go to directly also gets a list at the top.**
   When users think of "the zones" rather than of "this stream's zones", add
   `/zone`, with all zones on all streams and "New zone" (with the stream as a
   field of the form). Its items open the zones' pages below their streams. It
   has no pages of its own below it.
8. **An entity's aspects are pages below its key, named for what they hold.**
   The entity's page shows what everyone needs to see of it: its live state,
   its children, its recent events, and the action on the whole entity
   ("Remove device"). The aspects go below it: `.../events` (its readings and
   events over a time range), `.../settings` (its forms and "Delete"),
   `.../details` (technical details for experts). What the brief says only some
   users need goes one level down, never onto the entity's page. An aspect page
   exists only where it applies: `/model/<model>/settings` only for the models
   users can change.
9. **Readings and events have no pages of their own.** They show on the page of
   the entity that produces them (`.../events`) and, when users compare them
   across all entities, on one view at the top (`/detections`).
10. **Not every entity needs a route.** An entity that users see only as part of
    its parent (the cameras a device detects, a stream's state) is shown on the
    parent's page.
11. **The routes at the top are the main menu**, in the order users need them,
    not in the order of the tree: Streams before Devices when people come for
    the streams.

## An example

The route tree of a video analytics app: devices run streams, a stream has
zones, a stream uses a model, detections are its events. The streams run on
devices, but start their own branch (rule 6), and Devices comes last in the
menu:

```text
/                            Now: summary strip, snapshot wall, streams needing attention, latest events
/stream                      Streams: all streams on all devices, "Add stream" (device in the form)
/stream/<stream>             Stream: live view, its device, zones table, recent events
  .../zone                   Zones and lines: click to draw, "New line or zone"
  .../zone/<zone>            Zone: draw the zone, edit form, "Delete"
  .../events                 the stream's events: date filter, events table, crossings charts
  .../settings               Stream settings: basic and advanced forms, "Delete stream"
/detections                  Detections: crossings and occupancy on all devices, events
/model                       Models: standard and custom models, "Register a custom model"
/model/<model>               Model: details, readiness per device
/model/<model>/settings      custom model settings (custom models only)
/device                      Devices: the list of devices, when each last reported
/device/<device>             Device: detected cameras, the streams it runs, "Remove device"
/device/<device>/details     technical details (experts)
Route segments: stream, model and device '2', zone '4'.
```

## From the tree to pages, menus and tabs

In the board's page tree, each type segment is a named page and each `<key>`
is a `*` page below it (`stream` → `*` → `zone` → `*`). A `*` page matches
any segment at its position. Its widgets read the key from the URL with a
`useRoute` filter whose `value` is the segment's index, so every widget on an
entity's page shows that entity (on `/stream/<stream>`:
`{"column": "stream_id", "operator": "=", "value": "2", "dataType": "string", "useRoute": true}`).

How a link resolves decides how menus are built:

- **A route with a leading `/` is absolute**, from the board's home.
- **A route without one replaces the last segment** of the current URL. From
  `/stream/<a>` the route `<b>` opens `/stream/<b>`, but from the stream's tab
  page `/stream/<a>/events` it opens `/stream/<a>/<b>`, which is no page. A
  relative route therefore works only on the pages next to its target.
- **A segment that is exactly `*`** is replaced by the current URL's segment
  at that position, and `{{name}}` by the item's variable whose `label` is
  `name`.

Two things follow:

- **An entity's aspects are its tabs.** A widget-navbar with absolute routes
  that copy the keys from the current URL (`/stream/*/events`,
  `/stream/*/settings`), titled with the entity's name and linking to its page
  (`/stream/*`).
- **A menu builds each item's absolute route from the keys in its row**: a
  constant route with a `{{placeholder}}` per key in the item's `format`, and
  `variables` binding each placeholder to its key column, never the key column
  alone. The item's label is the entity's name. For the zones of a stream:

  ```json
  {"label": "name",
   "route": "$str:/stream/{{stream}}/zone/{{zone}}",
   "variables": [{"label": "$str:stream", "value": "stream_id"},
                 {"label": "$str:zone", "value": "zone_id"}]}
  ```

  The widget puts each row's values in (URL-encoded). On a page below
  `/stream/*` the stream's key is in the URL already, so
  `$str:/stream/*/zone/{{zone}}` with only the `zone` variable leads to the
  same pages. This works at any depth and on every page the menu is on, for
  the list of streams (`$str:/stream/{{stream}}`), a stream's zones, a
  device's streams and the list at the top of a nested type (`/zone`) alike,
  so every menu stays bound to its entity table and follows new and deleted
  entities live. A menu that lists entities of several parents (all zones of
  all streams) needs every key in the route as a variable, which is why each
  table carries the keys of all entities above it (rule 3).
- **Name a placeholder after the entity**, never after a URL parameter that a
  filter on the board sets (choose another name if a filter uses it): when
  the page has a URL parameter of that name, the board fills its value into
  `{{name}}` before the menu fills in its own, and every item gets that one
  value.
- **A missing key column belongs in the table**, not in a transform that
  computes the route: a transform follows new and deleted entities only on its
  schedule tick or when the app's code refreshes it, never by itself. Only
  where the table cannot be changed, compute the route in a transform
  (`'/line/' || line_id || '/station/' || station_id AS route`), bind the
  item's route to that column, and keep the transform's schedule short.
