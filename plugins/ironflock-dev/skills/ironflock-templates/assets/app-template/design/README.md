<!-- TODO: these documents describe the starter's example app. Rewrite each one
for this app from the interview's answers, and delete this comment in every file. -->

# App Starter: design

How App Starter is built and why, for the people and coding agents who change
it. `README.md` in the app's root is the description for the people who install
the app; this folder is for those who develop it.

| Document | What it holds |
|---|---|
| [architecture.md](architecture.md) | The parts of the app, what runs where, which tables exist, who writes each one, and how data flows between the devices and the board |
| [entities.md](entities.md) | The entity model: what the app deals with, how each thing is identified, how the things relate, who writes them and what users do with them |
| [board.md](board.md) | The board's design: who looks at it and where, the route tree, what each page shows and offers, the look and the state colours |
| [decisions.md](decisions.md) | The design decisions, newest first: what was decided, why, and what was left out |

## Purpose

- **Users:** the people who run the machines connected to the devices, at a
  desk or a laptop.
- **Goal:** see at a glance whether every machine runs within its temperature
  limit, and set that limit once for all devices.
- **Value:** nobody has to walk to a machine to read it; a machine running too
  hot shows up on the board within seconds; a limit changes everywhere at once,
  also on devices that are offline at the time.
- **Not in this version:** alarms by e-mail, per-device limits, history beyond
  the tables' retention.

## Keeping this folder current

- Read these documents before changing the app.
- Every change that makes a document wrong updates it in the same change: a new
  table or column, a new entity or relation, a new page or route, a new
  parameter, port or device function, a different look.
- A decision with a reason worth keeping (a choice between alternatives, a
  constraint, something deliberately left out) gets an entry in decisions.md.
- Describe what is, not what was: rewrite a section that no longer holds
  instead of appending a correction to it. The history is in decisions.md and
  in git.
