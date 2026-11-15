<!-- TODO: replace these with this app's decisions (see design/README.md). -->

# Decisions

Newest first. Each entry: the date, what was decided, why, and what was left
out. Add an entry when a choice between alternatives is made; rewrite the other
documents to match, and leave the entries themselves as they were written.

## The limit is a settings table, not a parameter

**Decision:** the temperature limit is a row in `settings`, written by the
board's form and applied by every device.
**Why:** it applies to all devices at once, users change it while the app runs,
and the table keeps who changed it when. A parameter is set per device or
device group in the app's settings, not on the board.
**Left out:** per-device limits; they would be a column of `devices`, written
by the board.

## The live view goes through the remote-access tunnel

**Decision:** `main.py` serves the live view on port 8080, the port template
opens a tunnel for it, and the board embeds the tunnel's URL from
`devices.ui_url`.
**Why:** the board works from anywhere, with IronFlock's sign-in in front of
the page; no device address is hard-coded.

## A device writes its state only when it changes

**Decision:** `devices` gets a row when the state changes, not with every
reading.
**Why:** the table stays a readable history of state changes, and the board's
latest filter shows the current state live either way.
