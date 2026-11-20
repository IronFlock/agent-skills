# Pages and navigation

This reference covers the page tree of board-template.yml (`layout` and its
`subRoutes`) and how users move between the pages: reachability, how menus
highlight their items, how a link resolves, and the navigation patterns. Which
pages a board has is decided first, with board-route-tree.md. The forms of
boards on which users create, edit and delete records are in board-forms.md. It
assumes the board's anatomy and the literal prefixes (`$str:`, `$num:`,
`$bool:`) from board-template.md, "Anatomy" and "Literal values".

## The page tree

`layout` is a tree of pages:

```yaml
layout:                         # /
    gridLayout: [...]
    subRoutes:
        machines:               # /machines
            gridLayout: [...]
            subRoutes:
                '*':            # /machines/<anything>: one page for every machine
                    gridLayout: [...]
```

- **Page names** use letters, digits, `.`, `_`, `-` and `*`. A `*` page matches any
  segment, and the widgets on it read the segment with `useRoute` filters.
- **Every page needs a `gridLayout`.**
- **A widget is on a page** when that page's `gridLayout` has an entry whose `id`
  is the widget's `layout_id`.
- **Shared widgets:** to show the same widget on several pages (a menu, say), add
  the same id to each page. Give it the same position on every page, because moving
  it in the editor moves it everywhere.

## Every page users see is reached by clicking

People move through a board only by clicking: nobody types a route, and a kiosk
screen has no address bar. So:

- **Every page users see must be reachable from the home page** (`/`) through a
  series of clicks, and **must lead back home.** A page that nothing links to
  cannot be opened, and a page without a way back traps its user. The validator
  follows every link from the home page the way the board does, and reports each
  such page it cannot reach, and each page with no way back, as an error.
- **A page that only holds the pages below it need not be reachable.** The route
  `/devices/*` needs a `devices` page above it, but users may open each device
  straight from a menu on another page and never see `/devices` itself. Give such
  a transient page no widgets (`gridLayout: []`), and the validator skips it. A
  page with widgets is one users see, so it must be reachable. If a link opens an
  empty page after all, the validator warns, because users see a blank screen.
  A data-driven menu's item routes are absolute, built from the key
  (`route: $str:/devices/{{device}}`, pattern 2), so the menu reaches
  `/devices/*` from any page: a relative route from `/` would open
  `/<device_key>`.
- **Only navigation widgets move between pages:** widget-navbar, widget-sidenav and
  widget-navbutton. A widget-table `button` or `image` cell opens its link in a new
  browser tab, so it cannot move inside the board. Use those cells for external
  links only.
- **Put the same menu on every page of one level, at the same position**, so it
  reads as the board's menu.

## How menu items are highlighted

widget-navbar and widget-sidenav (version 1.0.26 and later) compare an item's
route with the current route **segment by segment**, after filling in its
`{{variables}}` and `*` segments, and of all items that match they highlight
only **the most specific**:

- **An absolute item matches its page and every page below it.** `/machines`
  matches `/machines/press-1` too. An item for the home page (`/`) matches only
  the home page.
- **A relative item** (no leading `/`) matches a page whose route ends with it.
  An item `press-1` matches `/machines/press-1`, but not its tab page
  `/machines/press-1/history`, where the absolute item `/machines/press-1`
  stays highlighted. That is one reason why data-driven menus use absolute item
  routes (pattern 2).
- **The most specific match wins.** An item that names the current page beats
  one that names a section it is in, and a deeper section beats a shallower one.
  On `/reports/daily`, only `/reports/daily` is highlighted, not `/reports`.
  Segments are compared whole, so `/line` does not match `/lines`, and
  `/line/LINE-1` does not match `/line/LINE-10`.
- **Query parameters count.** An item route with `?state=open` matches only
  while the URL carries that parameter with that value, and beats the same route
  without it.
- **Two items with the same route are always highlighted together.** The
  validator warns about them.

What follows for menus:

1. **A Home item works.** It is highlighted on the home page only. The menu's
   **title** links home as well (`title: $str:Machine Monitor`,
   `route: $str:/`); the title is never highlighted.
2. **An overview can sit next to its sections.** A tab bar may hold "Overview"
   (`/line/*`) next to "Andon" (`/line/*/andon`): each is highlighted on its own
   page.
3. **A section's item stays highlighted on the pages below it**, as long as no
   more specific item of the same menu matches there. Use that: give each
   section one item, and connect the pages inside a section with their own links
   (see the patterns below).

**Versions before 1.0.26** compare by characters and highlight every item whose
route starts the current route. On them, an item for `/` is highlighted on every
page, `/reports` together with `/reports/daily`, `/line` on `/lines`, and the
data-driven item `/line/LINE-1` on `LINE-10`'s pages. Pin 1.0.26 or later for
the board's menus. Where a board keeps an older version, link home only from the
title, keep a route that starts another item's route out of the same menu, and
give data-driven ids the same number of digits (`LINE-01` … `LINE-24`). The
validator checks the first two against the pinned version.

widget-navbutton is never highlighted. That makes it the right widget for a single
link such as "Home", "Back to the list" or "Manage documents".

## How a link resolves

- **`/machines` is absolute**, from the board's home.
- **`press-2`, with no leading slash, replaces the last segment** of the current
  URL. From `/machines/press-1` it goes to `/machines/press-2`. From
  `/machines/press-1/history` it goes to `/machines/press-1/press-2`, which has
  no page, so the board opens its home page. From `/machines` (no trailing
  slash) it goes to `/press-2`; only from `/machines/` would it reach
  `/machines/press-2`. A relative route therefore works only on the pages that
  sit next to its target, which is why the items of a data-driven menu are
  always absolute, built from the row's keys (pattern 2), and never the key
  column alone. A trailing slash only changes where a relative link on that
  page leads; link pages without one (`/machines`).
- **A segment that is exactly `*`** is replaced by the current URL's segment at
  that position, and `{{name}}` by the item's `variables` entry with `label: name`.
  A `*` needs a segment at its position: on `/machines`, the route
  `/machines/*/trend` has no second segment to copy, so the link opens
  `/machines/trend`.
- **A route that contains `*` loses its trailing slash.** `/line/*/andon/` opens
  `/line/LINE-1/andon`, so relative links on that page lead next to it
  (`/line/LINE-1/<id>`), never below it. Item routes built from the row's keys
  (patterns 2 and 3) are not affected.

## Navigation patterns

1. **Sections.** One widget-navbar or widget-sidenav on every page. Its title links
   home, and each item opens one section (`/machines`, `/alarms`, `/settings`).

2. **A list and its detail pages** (`/machines` and `/machines/*`). A data-driven
   menu lists one item per row. Build each item's absolute route in the item's
   `format`: a constant route with a `{{label}}` placeholder for the key, and a
   `variables` list that binds the placeholder to the key column of the row.
   The widget puts each row's value in (URL-encoded), so the menu stays bound to
   the entity table and is live:

   ```yaml
   navItems:
       tableRef:
           tablename: machines
           format:
               label: name                               # what users see
               iconName: $str:precision_manufacturing    # Material icon name
               route: $str:/machines/{{machine}}         # absolute: /machines/<id>
               variables:
                   - {label: $str:machine, value: machine_id}   # the generated id
           queryParams:
               limit: 50
               filterAnd:
                   - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
   ```

   Never bind `route` to the key column alone (`route: machine_id`). That is a
   relative route, which replaces the last segment of the current address: it
   works on `/machines/` and `/machines/press-1`, but on a tab page of the
   machine (`/machines/press-1/history`) a click opens
   `/machines/press-1/press-2`, which has no page, and no item is highlighted.
   An absolute route works on every page, also when tab pages are added later.

   Put this menu on `/machines`, on `/machines/*` and on the pages below it, and
   link to the list as `/machines`, without `*`. On the `*` page, filter every
   widget with `{column: machine_id, operator: '=', value: '2', dataType: string, useRoute: true}`.

3. **Detail pages below a `*` page** (`/line/*/andon/*`), from a menu anywhere.
   The route holds every key on the way, each with its own placeholder and
   variable:

   ```yaml
   navItems:
       tableRef:
           tablename: andon_requests          # carries line_id and request_no
           format:
               label: request_no
               route: $str:/line/{{line}}/andon/{{request}}
               variables:
                   - {label: $str:line, value: line_id}
                   - {label: $str:request, value: request_no}
           queryParams:
               limit: 50
               filterAnd:
                   - {latest: true, column: '', operator: '=', value: '', dataType: boolean}
                   - {column: line_id, operator: '=', value: '2', dataType: string, useRoute: true}
   ```

   On a page below `/line/*`, the line's key is in the URL as well, so
   `route: $str:/line/*/andon/{{request}}` with only the `request` variable
   leads to the same pages. A menu that lists entities of several parents (all
   andon requests of all lines) needs every key in the route as a variable. The
   table has to carry the keys of all entities above it in the route
   (app-architecture.md, "The entities"). Add a missing key column to the table
   rather than computing the route in a transform: a transform follows new and
   deleted entities only on its schedule tick or when the app's code refreshes
   it, never by itself.

4. **An entity with an overview and sections** (`/line/*`, with `/line/*/andon`,
   `/line/*/reports` and so on below it). A widget-navbar is the entity's tab
   bar. Its title is bound to the entity's name and links to the overview
   (`route: $str:/line/*`), and its items open the sections
   (`/line/*/andon`). An "Overview" item for `/line/*` may sit next to them
   (rule 2; before version 1.0.26 leave it out, the title is the way there).
   When the tab bar is the only menu on these pages, put a widget-navbutton next
   to it as the way home (`title: $str:Home`, `iconName: $str:home`,
   `route: $str:/`).

5. **Pages within a section** (`/line/*/sop` and `/line/*/sop/manage`). Connect
   them with widget-navbutton ("Manage documents", "Back to documents"). The
   section's item stays highlighted on both.

6. **Records that users create, edit and delete** (master data, settings). A
   data-driven widget-sidenav lists the records (pattern 2 or 3) and opens one
   page per record (`/settings/machines/*`). A "New" form, an edit form and a
   separate delete form do the rest: board-assets.md has the rules, and
   board-forms.md the delete form in YAML and how the patterns above serve a
   board that manages assets.
