# Looking at the board

After you built or restyled a board, look at it. The checks you then run on
the picture are in [board-critique.md](board-critique.md).

With the `ironflock` plugin's connection you can get a picture of a board and
a report on its widgets. Looking changes nothing. It takes several seconds, up
to a minute when the service is busy; an account can look once at a time and
four times a minute. The key needs the scope to read data.

- **The app in development:** `get_dev_dashboard_image` with `app_key` and
  `swarm_key`. It shows the working copy's `.ironflock/board-template.yml`
  with the app's development data in the project. Cloud only. `swarm_key`
  comes from `list_projects`, `app_key` from `list_project_apps`.
- **An installed board:** `get_dashboard_image` with `swarm_key` and
  `dashboard_key` (from `list_dashboards`).
- `page` names the page to show (home without it), `full_page` shows the
  page's whole height, `width` and `height` set the window.

**When.** After you built a new board, after a change of layout or style that
affects a whole page, and when the user asks how it looks or says that
something looks wrong. Not after a change to what one widget shows, and not
again without a change in between: the picture would be the same.

**How to judge.** The report names the page shown, the board's pages, whether
the picture had settled, and each widget that is not drawn, with its state
and reason. Each of these is a finding: fix it, or say why it stays.

- **Empty:** its data had no rows. Right for an app without data yet, wrong
  for a filter that excludes everything.
- **No data in time:** nothing arrived within 15 seconds.
- **Data unavailable:** the data it reads could not be reached; the tile says
  "Data source unavailable". Check that the table it names exists.
- **No right:** the key's owner may not read that data, or access to another
  app's data was not granted.
- **Failed to load:** the widget itself could not be loaded. Check its
  package name and version.
- **Failed while drawing:** check its configuration.
- **A tile without a widget:** the layout has a tile that no widget fills.
- **Pending:** it had not finished when the time was up.

Then run the five checks of board-critique.md on the picture. Look at the other pages only when
their layout changed. Correct, and look once more: one round.

**When no picture can be had.**
- The development tool answers that it is unavailable: say what is missing.
  Either the working copy has no board (add `.ironflock/board-template.yml`)
  or the app was never started in development in that project (start it
  there once).
- It answers that it is busy: wait and try once more.
- On an appliance, or when the platform has no such tool, go on with the
  checks from the definition, and tell the user that the board was not
  checked visually.
