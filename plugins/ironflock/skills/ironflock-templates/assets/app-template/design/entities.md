<!-- TODO: rewrite for this app (see design/README.md). -->

# Entities

What the app deals with, and how each thing is identified. Every table, page and
form follows from this model.

| Entity | Key | Table | Written by | On the board |
|---|---|---|---|---|
| device, with the machine at it | `device_id`, the device's own key | `devices` | the device, about itself; users delete it | list, state, live view, delete |
| measurement | `device_key` + `tsp` | `measurements` | the device | trends, current values |
| settings | none: one row for all devices, the newest in force | `settings` | the board's form | the Settings page |

## Relations

- A measurement belongs to the device that took it (`measurements.device_key`,
  the same number as `devices.device_id`).
- The settings apply to every device; nothing refers to them by key.

## Rules the model follows

- One entity table per entity, keyed by what identifies it
  (`maintainLatestFlagFor`); no generated ids.
- A table that refers to an entity carries its key, and the keys of every
  entity above it, so the board can filter by any of them and build the route
  to it from the row.
- An entity users create and change gets a `deleted` column, a list bound to
  its table, a "New" form in a dialog, and a detail page with edit and delete.
  App Starter has none yet: its devices come from IronFlock.
- A device registers itself at start and can never unregister, because nothing
  tells a device that is offline from one that is gone. So `devices` has a
  `deleted` column and the device's page a "Delete" button; nothing deletes a
  device automatically. Its key is `device_id`, which the device writes, since
  the board's delete row cannot set `device_key`. Registration writes
  `deleted: false`, so a device that comes back reappears.
