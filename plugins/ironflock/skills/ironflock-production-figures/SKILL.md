---
name: ironflock-production-figures
description: Production figures of machines from IronFlock data - OEE and its three parts (availability, performance, quality), TEEP, output, scrap rate, stops and downtime ranked by minutes and by count, MTTR, MTBF, losses - and finding out why a machine or line stopped, slowed down or made scrap. Use this whenever the user asks for such a figure ("what is our OEE", "Wie hoch ist die Verfügbarkeit von Presse 3", "which stops cost us most", "Stillstände je Schicht"), asks why a machine was down ("why was line 2 down so often last week", "warum steht Presse 3 ständig"), or wants these figures in a transform, an app or on a board ("build me an OEE board"). Queries run as ironflock-data describes; app files are written with ironflock-templates.
metadata:
  mcp-tools: get_schema execute_sql save_transform check_app_status query_audit_log
  min-api-version: 2.0.0
---

# Production figures from IronFlock data

OEE, its parts, stops and losses are computed from the rows machines write
into an IronFlock project: state changes, samples, part counters, events.
Two kinds of work use this skill:

- **Answering from an instance.** The figures come from the project's
  database through IronFlock's MCP tools. How queries are run there (the
  schema first, a time range, aggregation in SQL, result size, read-only,
  a yes before a transform is saved) is the skill `ironflock-data`; follow
  it.
- **Building an app** whose transforms and board show these figures. The
  app's `data-template.yml` (transforms) and `board-template.yml` are the
  skill `ironflock-templates` of the `ironflock-dev` plugin. If that skill
  is not available, tell the user to install the plugin
  (`claude plugin install ironflock-dev@ironflock`) and help with the SQL
  and the figures meanwhile.

## Which reference to read

| Task | Read |
| --- | --- |
| A figure: OEE, availability, performance, quality, TEEP, output, scrap rate | references/oee.md, and references/machine-data-sql.md before the first query |
| Stops, downtime, which stops or machines cost most, MTTR, MTBF, losses, prices | references/downtime-losses.md and references/machine-data-sql.md |
| Why a machine or line stopped, slowed down or made scrap | references/root-cause-checks.md and references/machine-data-sql.md; references/downtime-losses.md when it is about how often or how long |
| A transform that keeps such figures live, in a project or in an app | references/oee.md or references/downtime-losses.md, and references/machine-data-sql.md ("Putting OEE together") |
| A board with these figures | references/oee.md ("Show the parts apart"), references/downtime-losses.md, and "Boards" below |

## Rules

- **Find the inputs before computing.** `get_schema`, then a few rows of
  each table involved: the state values, a stop reason, a part counter or
  part rows, good and scrap, the product. What a state or reason value
  means comes from the column descriptions or from the user, never from a
  guess.
- **Ask for what the data does not hold**, once and all at the same time:
  the planned production time (shift times, breaks, planned stops), the
  ideal cycle time per product, which states count as running and which
  stops are planned, and when it matters the plant's time zone and the day
  a night shift belongs to. Never put a default or a typical value in
  place of an input. Without it, the figure that needs it is not
  computable: say which input is missing and report the rest. A stand-in
  from the data (such as the best rate shown over a period) is used only
  when the user agrees, and named next to every figure it affects.
- **Compute in SQL.** One `execute_sql` query that returns the inputs and
  the parts per machine and period, with run time, stops and parts clipped
  to the planned production windows; state the figures as the result gives
  them, never worked out by hand. Aggregate per machine and shift or day,
  so the result stays small.
- **Report the parts with their inputs and period.** OEE always with
  availability, performance and quality beside it, per machine (or line),
  with planned time, run time, total and good count, ideal cycle time, the
  period and the time zone, the time left out for lack of state data, and
  each assumption next to the figure it affects. Where a part counter gives
  two counts (references/machine-data-sql.md), report the range and ask
  about the flagged steps. Stops ranked by minutes and by count side by side, the share
  without a usable reason first. Plain words, in the user's language; the
  German terms are in references/oee.md.
- **Keep figures live with a transform.** One row per machine and shift
  (or hour or day) with the input columns and the parts; a second
  transform on top sums the inputs and divides again for longer periods or
  several machines (quality weighted by ideal cycle time, as
  references/oee.md says), because averaging a ratio column over rows is
  wrong. An input the user gave is named with its source in the
  transform's description. In a project, save it with `save_transform` as `ironflock-data`
  describes; in an app, it goes into `data-template.yml`.
- **Why something happened.** Safety first, as references/root-cause-checks.md
  says. No rows is not a stop: when the data stopped arriving, check the app
  that collects it (`check_app_status`, the skill `ironflock-fleet`) before
  the machine. Changes to the machine's apps and devices are in the audit
  log (`query_audit_log`, as `ironflock-fleet` describes). Give ranked
  candidate causes with evidence for and against, never one verdict.

## Boards

Top to bottom: for the current shift or day, per machine or line, OEE with
availability, performance and quality as separate figures beside it; then
the stops by minutes and by count side by side; then the trend of OEE and
its parts per shift or day; then the details. A part that cannot be
computed is shown with its reason, never as 0 and never left out. In an
app, `ironflock-templates` decides the widgets and bindings.

## Origin

references/oee.md, references/downtime-losses.md and
references/root-cause-checks.md are adapted from the claude-for-manufacturing
plugin by Anthropic and are under the Apache License 2.0; NOTICE in this
folder says what was changed.
