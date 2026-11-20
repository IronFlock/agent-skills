<!-- Adapted from the claude-for-manufacturing plugin, version 1.0.0, by Anthropic, under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten for machine data in SQL tables. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-production-figures (IronFlock/agent-skills), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# Root-cause checks on machine history

This file covers finding out why a machine or line stopped, slowed down or
made scrap, from what its data holds: state and alarm history, sensor
readings, part counts, and records of changes (settings, recipes, products,
maintenance, software). The order is: safety, the event, the coverage of the
data, the checks, ranked candidate causes, the report. Stop durations and
counts are derived as in `machine-data-sql.md`.

## Safety first

When the request or the data shows a possible hazard, name it before any
cause: a seized or locked moving part; a guard, door, interlock or
emergency-stop alarm, or a bypassed guard; stored energy (hydraulic or
pneumatic pressure, springs, a raised or loaded axis); an electrical fault
(a trip, a burnt smell, damaged cables); over-temperature or a leak; a fault
cleared by restarting that keeps coming back. An uncertain hazard is a
hazard. Whenever an answer suggests a check at the machine, it opens with:
"Follow your plant's lockout procedure before anyone works on this machine.
This is not a safety assessment." No suggested check comes before that line.

## The event and the data around it

- Fix the event first: which machine, when exactly (from the state or alarm
  rows), and the symptom in the user's words. Do not turn the symptom into a
  cause yet.
- Check that the data covers it: rows right up to the event and after it.
  A gap just before the event means the deciding window is missing; say so,
  and never reason from the neighbouring data as if it were the event.
- Rows from different devices or tables can carry different clocks. Before
  relating two sources, find one event visible in both (a stop in the state
  rows and the drop of power or speed in the readings) and check that they
  agree. If they cannot be aligned, do not correlate them, and say which
  conclusions still hold (a clustering by product does not depend on
  clocks). Time stamps in the future mean a clock is wrong.

## The checks

Each check is computed with a query, and its numbers are reported, also
when it found nothing.

**1. Drift before the event.** Compare the readings of a window before the
event (hours to a day) with a baseline before that (for example the week
before, same product), both only while the machine ran: readings taken
while stopped or warming up look like drift. (In the example the readings
carry the state; otherwise keep only readings that fall inside the run
intervals derived as in `machine-data-sql.md`.) Report the slope per hour, the
shift of the mean, and the hours whose mean lies outside the baseline's
range of hourly means. A reading that climbed for hours without reaching its
alarm limit is exactly what a threshold misses.

```sql
WITH hourly AS (
  SELECT time_bucket('1 hour', tsp) AS h, avg(temperature) AS v,
         tsp < timestamptz '2026-11-19 06:00 Europe/Berlin' AS baseline
  FROM readings
  WHERE machine_id = 'P-3' AND state = 'RUN'
    AND tsp >= timestamptz '2026-11-12 06:00 Europe/Berlin'
    AND tsp <  timestamptz '2026-11-19 12:00 Europe/Berlin'   -- the event
  GROUP BY 1, 3
),
band AS (
  SELECT percentile_cont(0.01) WITHIN GROUP (ORDER BY v) AS lo,
         percentile_cont(0.99) WITHIN GROUP (ORDER BY v) AS hi
  FROM hourly WHERE baseline
)
SELECT h, v, v < lo OR v > hi AS outside_baseline
FROM hourly, band WHERE NOT baseline ORDER BY h;
```

The slope over the window before the event is
`regr_slope(temperature, extract(epoch FROM tsp) / 3600)` (units per hour).
Three shapes mean different things: a steady climb points at wear (bearing,
tool, filter); a step points at something discrete (a part let go, a
setting changed); a spike that recovered points at an intermittent fault.

For measurements per part (a dimension, a weight) use an individuals chart:
centre line = baseline mean, limits = centre +/- 2.66 x the mean moving
range (mean absolute difference of consecutive values). Signals: a point
beyond a limit, eight points in a row on one side of the centre (some
plants use nine), six in a row steadily rising or falling. Control limits
describe the process, specification limits the drawing: report against
both and label them. A process can be within specification and drifting.

**2. Clustering.** Group the events (stops of one reason, scrap, alarms) by
what the data holds: shift, machine, product or recipe, tool, material lot.
Always against the base rate: events per run hour or per thousand parts,
never counts alone. 11 of 14 stops on the night shift says nothing when the
night shift ran 80% of the hours (1.8 against 2.0 stops per ten run hours).
With fewer than about five events in a group, say it is too few to tell.
Grouped by operator, name the pattern, never the person's competence: the
cause sits in an instruction, a setting or training, and an analysis that
ends on a person stopped one question early.

**3. What changed just before.** List every change in a window before the
first occurrence: settings and recipe rows, product changes, tool changes,
maintenance and repairs, new material, software or configuration changes of
the machine's apps and devices. A repair is a change and a candidate too.
For each change, compare the event rate (per run hour) in equal windows
before and after it, and only across sources whose clocks agree.

**4. Recurrence.** Look for the same reason or alarm earlier on this
machine and on machines of the same type, and what changed after it then.
No earlier record in the data is "no history found", not a first
occurrence: the data may start later than the problem.

## Ranking candidate causes

- Give ranked candidates, never one verdict. A confident wrong cause ends
  the search, the fix fails, and the problem returns.
- Each candidate is a chain (cause, mechanism, symptom) with the evidence
  for it, the evidence against it, and the cheapest test that would confirm
  or rule it out. Rank by the strength of the evidence; propose the cheapest
  test that tells the leading candidates apart.
- When two candidates are supported equally, say so and name the test that
  separates them; do not break the tie to look decisive.
- A candidate without evidence in the data (experience, a hunch) is stated
  as a hypothesis, not left out.
- A coincidence in time is not proof. A candidate stays a candidate until a
  test confirms it.
- Push past the symptom: "the tool broke" is a symptom; "the tool change
  interval was set for a softer material" is a cause a change can remove.

## Reporting

In this order: the safety line when it applies; the event (machine, time,
symptom, how well the data covers it); the ranked candidates; the checks
that found nothing, with their numbers ("stops did not cluster by shift:
1.8 to 2.0 per ten run hours"); the checks that could not run and why (no
product column, clocks not aligned); the next test, and which data would
make the next investigation easier (a reason for every stop, a product
column). Found, clean and not run are three different results; never merge
them.
