<!-- TODO: rewrite for this app (see design/README.md). -->

# Board

The full design of `.ironflock/board-template.yml`. The template's comment
header carries the short version; both change together.

## Brief

- **Who looks at it, where:** the people who run the machines, at a desk or a
  laptop.
- **What they look for first:** whether every machine is within its limit, and
  which one is not.
- **What they change:** the temperature limit, on its own page.
- **Look:** the `office` preset, since the board is read at a desk.
- **States and colours, the same on every widget:** OK green `#16a34a`,
  TOO_HOT red `#dc2626`, NO_READING grey `#64748b`.

## Route tree

| Route | Page | Shows | Action |
|---|---|---|---|
| `/` | Overview | every device's temperature and state, the 24-hour trend | none |
| `/devices` | Devices | the device list, and a hint to pick a device | none |
| `/devices/<device_id>` | Device | the device's live view above its readings | "Delete" (a device that is gone) |
| `/settings` | Settings | the limit in force and the saved settings | the settings form |

The main menu (a sidenav on every page, its title linking home) has Devices and
Settings. The device list on `/devices` and `/devices/<device_id>` is a
data-driven sidenav bound to `devices` with `{latest: true}` and the filter on
`deleted`, so a new device appears in it within a second, and a deleted one
leaves it. Each item's route is absolute, built from the row's `device_id`
(`/devices/{{device}}`).

## Pages

- **Overview:** the top band holds one temperature readout per device and,
  next to it, the device table with its state column; the 24-hour temperature
  trend fills the rest.
- **Device:** the embedded live view takes the top part, with a red "Delete"
  button below it that asks for confirmation and leads back to the list; this
  device's readings of the last 24 hours (filtered by the route's segment 2)
  fill the rest.
- **Settings:** the form shown in its tile, prefilled with the limit in force;
  the saved settings below it.

The toast on every page shows the errors the app reports.
