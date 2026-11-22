# Boards that manage assets

This reference covers the standard shape of a board on which users inspect,
create, change and delete assets: the main menu, the list of each asset type,
the "New" form, the edit and delete forms, the detail and tab pages,
sub-assets, and the tiling of an asset's page. It builds on
board-route-tree.md, which says how the pages and routes follow the entities
and how a menu builds its item routes.

Configuration fragments in this reference write constants with their type
prefix (`$str:`, `$num:`, `$bool:`). Whether a constant needs the prefix where
you write it is in the instructions of your surface; the fields and their
values are the same either way.

Many boards let users inspect, create and change assets of a few types:
machines, lines, sites, recipes. The asset types are the app's entities that
users manage, so the entity model decides the menu, the lists and the forms.
Build these boards the same way every time, so users find their way around
without having to think about it.

The examples use the asset type machine (entity table `machines`, key
`machine_id`, a `name` column and a boolean `deleted` column) with its type page
`/machine` and its detail page `/machine/<machine>` (the `*` page
`/machine/*`), and the sub-asset station below line. Name the routes after the
asset types in the data, in one form on every level, as board-route-tree.md
prescribes.

## 1. The main menu: the asset types

The asset types are the main menu. A widget-navbar (or widget-sidenav) has one
fixed item per route at the top of the route tree: the asset types that belong
to no other (`/machine`, `/line`, `/recipe`), and the views across all assets.
Its title links home, and it is on every page. Each item opens the page of that
asset type.

## 2. The type's page: the list of its assets

An asset type's page lists its assets in a widget-sidenav. For assets that users
create and change, the list is a data-driven widget-sidenav (`navItems` as a
tableRef) with one item per asset, labelled with the asset's name, whose route
is absolute and built from the asset's key: `route: $str:/machine/{{machine}}`
with a variable that binds `machine` to `machine_id`. Every item then opens
`/machine/<key>` from any page the list is on, and stays highlighted on the
asset's tab pages. Never bind the route to the key column alone: that is a
relative route, which replaces the last segment of the current URL, so it opens
a page that does not exist from a tab page, and its item is not highlighted
there. Name the placeholder after the entity, never after a URL parameter that a
filter on the board sets.

The list is on the asset type's page and on every page of an asset below it. Its
title names the type ("Machines") and links to the type's page (`/machine`). The
type's page itself shows an overview of all its assets, such as a widget-table
of them or the fleet's KPIs, and never stays empty.

## 3. The master list reads the asset table, never a view

The widget that lists the assets of a type (the sidenav or data-driven navbar
that leads to each asset, and the overview table) is that type's master list. It
is bound to the asset's entity table itself, with the latest filter
(`{"latest": true}`, the newest row per asset) and the filter on `deleted`
(section 4), never to a transform. An asset created with the "New" form then
appears in the list, and a deleted one disappears, in under a second, because
the filters are live: a new row replaces the asset's row in the widget, and a
deleting row removes it.

A transform reaches the board only on its schedule tick, or, for an app's own
transform, when the app's code refreshes it, while the board's forms write the
table directly. A list bound to a transform leaves users looking at an asset
they just deleted, or missing the one they just created. Bind the list to the
table even when a view with more columns exists. Other widgets may use the view:
a status overview from a view (each asset's state and counts) is a second widget
next to the master list, never instead of it and never where users open, edit or
delete an asset. Never put a transform between the table and these widgets to
pick the newest row or hide deleted records; it would only delay them.

Nested lists are no exception: the sub-asset table carries the keys of every
entity above it, and each item's route is built from the keys in its row
(section 9).

## 4. Deleted assets stay out of every list

When the asset's entity table has a delete flag (a boolean column such as
`deleted`, the column a delete form writes, section 7), every widget that lists
its assets is bound with the latest filter and a filter that hides flagged rows:
the sidenav, the overview table, navbar items, the options of a dropdown or of
a form's dropdown field, markers on a map, any list, not only the one next to
the edit form. The filter is an OR group of `deleted` IS NULL and `deleted` =
false, since rows written without the flag carry NULL:

```json
{"combinator": "OR", "filters": [
    {"column": "deleted", "operator": "IS NULL", "dataType": "boolean"},
    {"column": "deleted", "operator": "=", "value": false, "dataType": "boolean"}]}
```

With the latest filter in the same list, a row with `deleted: true` removes its
asset from the widget the moment it arrives, because the newest row per asset is
picked first and this condition hides it afterwards. An older, undeleted row
never comes back. The "New" and edit forms need no field for the flag. To let
saving restore a deleted asset, give the edit form a hidden checkbox on
`deleted` with `defaultValueBoolean: $bool:false`.

Hide deleted assets by default. Show them only where the user explicitly asks
for them (a "Show deleted" switch, a recycle bin, an audit view). A switch is a
third condition in the same OR group, which reads a URL parameter that a
widget-filter-dropdown sets (`parameterKey: $str:show_deleted`, with the option
"Show deleted" of value `true`):

```json
{"column": "deleted", "operator": "=", "value": "show_deleted", "dataType": "boolean", "useFilter": true}
```

An unset parameter drops its condition, also inside a group, so the filter is
off until the user switches it on.

## 5. "New": a floating action button on the list

"New" is a floating action button on top of the list of section 2. A
widget-form with `formButton: $bool:true` opens the create form in a dialog, and
it shows a round floating action button unless `formButtonStyle.fab` is false.
Lay it over the top of the sidenav, in the sidenav's header next to its title: a
small tile (about 7 × 7 cells for the default button) inside the sidenav's
columns, with `z: 1` and a transparent tile border and background. Put it on
every page that has the sidenav, at the same position. This overlap is
intended, as is that of the empty tiles of the dialog forms (section 7).

On a board people touch, the round button at its touch size would cover the
list's first items. There the "New" form is a button with text
(`formButtonStyle.fab` false, `label` "New machine", `size` large, `fullWidth`
true) in a band of its own above the list: the list's columns, 7 rows,
`fixedWidth` and `fixedHeight`, the list starting below it
(board-interaction.md, "Sizes on a board people touch").

Its fields are a hidden key field with `generateId: $bool:true` (widget-form
2.2.0 or later), which saves a new UUID as the asset's id (users never type or
see it), the asset's name (required) and what else a new asset needs:

```json
[{"label": "$str:Machine ID", "type": "$str:textfield", "hiddenField": "$bool:true",
  "generateId": "$bool:true",
  "targetColumn": {"tablename": "machines", "column": "machine_id", "dataType": "string"}},
 {"label": "$str:Name", "type": "$str:textfield", "required": "$bool:true",
  "targetColumn": {"tablename": "machines", "column": "name", "dataType": "string"}}]
```

The edit and delete forms leave `generateId` off and carry the id over from the
record in their hidden key field (`preFilledValue`), so a rename changes only
the `name` column.

## 6. The detail page

Clicking an asset opens its detail page (`/machine/*`). Every widget on it
filters by the asset's key in the route: `useRoute` on segment `'2'`, with the
latest filter on entity tables. Where the page shows the asset's current fields
(its settings, its nameplate) rather than editing them, that is a
widget-markdown card laid out in HTML, never a widget-table with one row.

## 7. Editing and deleting an asset

Editing and deleting take two widget-forms. The **edit form** is prefilled
from the asset (`preFilledValue` valueRefs with the latest filter), and the key
itself is a `hiddenField`, so a save updates that asset.

The **delete form** is a separate widget-form: from widget-form 2.0 on, a form
has no delete button or delete setting of its own (1.x had `deleteButton`,
`deleteFlagColumn` and `deleteNavigationRoute`; never use them). A delete form
is a form whose Submit says "Delete" (`buttonLabels` with `submitLabel`
"Delete" and `cancelLabel` "Keep", a red `accentColor`, a title such as "Delete
this machine?") and that writes exactly two fields, both `hiddenField`: the
asset's key, and a checkbox on the delete flag with
`defaultValueBoolean: $bool:true`. A save writes the key with `deleted` true,
so the asset drops out of every list.

Say what the delete does, as a fact, in a third entry of `type` `section`,
which writes nothing and is shown above the dialog's buttons (a dialog does
not show `subTitle`): "It leaves every list. Its recorded data is kept." The
red is the preset's alarm red (board-interaction.md, "Contrast").

There are two equally good ways to offer them. Pick the one that suits the
board, or offer both:

- **Icons in the table that lists the assets.** The overview table gets a
  column of `type: $str:edit` with `styling.parameterKey: $str:edit` (a pen)
  and one with `styling.parameterKey: $str:delete` and
  `styling.iconName: $str:delete`, both bound to the key. A click writes the
  key into that URL parameter. The edit form and the delete form each have
  `formButton: $bool:true` and `openParameter: $str:edit` or `$str:delete`: on
  a board they show no button, and their dialog is open while the URL carries
  the parameter. Their valueRefs filter the key with that URL parameter
  (`value` `edit` or `delete`, `useFilter: true`), and they need no
  `submitNavigationRoute`: the dialog closes after a save or Cancel and drops
  the parameter. Their tiles stay empty on a board: about 7 × 7 cells over a
  corner of the table (both may share it), `z: 1`, with a transparent tile
  border and background.
- **On the asset's page** (its detail or settings page). The edit form is shown
  in the tile (`formButton: $bool:false`), its valueRefs filtered with
  `useRoute` on the key. The delete form is a red button next to it that opens
  a confirmation dialog: `formButton: $bool:true`, `formButtonStyle` with
  `fab: $bool:false`, the label "Delete", `iconName` `delete` and a red
  `bgColor`, its key field filtered with `useRoute`, and
  `submitNavigationRoute` back to the type's page (`/machine`), so it leads
  back to the list after the save. Give its tile about the size of the button
  (some 12 × 5 cells; on a board people touch, `size` large with `fixedWidth`
  and `fixedHeight`, 7 rows and 14 columns for "Delete", board-interaction.md),
  next to the edit form, not over it.

Never place a form button, such as the Delete button, at the bottom of the
screen (the last rows of the grid). Put it at the top of the asset's area or
next to the content it acts on, such as the top-right corner beside the edit
form or the asset's title.

## 8. Tab pages for further aspects

Other aspects of an asset get their own pages, behind tabs. The selected asset's
history, KPIs or alarms live on pages below its detail page
(`/machine/*/history`, `/machine/*/kpis`). A widget-navbar above the detail area
works as the tab bar, with absolute item routes (`/machine/*/history`). The
sidenav stays on these pages, and its item for the asset stays highlighted on
all of them, because its item routes are absolute (section 2) and a menu
highlights an absolute item on its page and every page below it, as long as no
more specific item of the same menu matches there (widget-navbar and
widget-sidenav 1.0.26 and later). The tab bar's title is bound to the asset's
name and leads to its detail page (`route: $str:/machine/*`), and an "Overview"
tab for the same route may sit next to the others, since only the most specific
tab is highlighted.

## 9. Sub-assets

Sub-assets repeat the same structure one level down. An asset's sub-assets (the
stations of a line) get their own data-driven widget-sidenav inside the asset's
detail area, with their own "New" button on top, and their own detail pages and
tabs (`/line/*/station/*`). The sub-asset table carries the parent's key, so the
sidenav builds each item's absolute route from its row:
`$str:/line/{{line}}/station/{{station}}` with variables binding `line` to
`line_id` and `station` to `station_id` (or `$str:/line/*/station/{{station}}`
on a page below `/line/*`). It reads the sub-asset table itself, live, like
every other master list. The same holds for the list at the top of a nested
asset type (all stations of all lines, at `/station`).

When the sub-asset table lacks a parent's key, add the column to the table.
Only where the table cannot be changed, compute the route in a transform
(`'/line/' || line_id || '/station/' || station_id AS route`) and bind the
item's route to that column; that list then shows new and deleted sub-assets
only on the transform's schedule tick, so keep that schedule short.

## 10. Pages without the list: an explicit back button

Hide a list when it costs more than it gives. When nested sidenavs leave too
little room, or users should focus on one asset, an asset's pages may leave the
list out and use the full width. Then put a prominent back button in the
top-left corner: a widget-navbutton with `iconName: $str:arrow_back` whose
route leads to the page with the list (`/machine`, or the parent asset's page).
Give the button an explicit route. An empty route means "one level up" (the
current route without its last segment), which is the page with the list only
from a page directly below it.

## 11. Tiling of an asset's tab page

An asset's tab page on a 96 × 64 grid:

```text
types   x=0  y=0  w=96 h=5   widget-navbar: Machines · Lines · Recipes (fixedHeight)
list    x=0  y=5  w=16 h=59  widget-sidenav of the machines (fixedWidth)
new     x=9  y=5  w=7  h=7   widget-form, floating action button, z: 1 (over the list)
tabs    x=16 y=5  w=80 h=5   widget-navbar: title = machine name; History · KPIs
content x=16 y=10 w=80 h=54  the tab's widgets
```

On a board people touch, the "New" button takes a band above the list
instead:

```text
new     x=0  y=5  w=20 h=7   widget-form, button with text, fixedWidth, fixedHeight
list    x=0  y=12 w=20 h=52  widget-sidenav of the machines (fixedWidth), style.fontSize 22
tabs    x=20 y=5  w=76 h=5   widget-navbar: title = machine name; History · KPIs
content x=20 y=10 w=76 h=54  the tab's widgets
```

The band is as wide as the list; the label "New machine" needs
ceil((99 + 112) / 12) = 18 of its 20 columns.
