# Production figures from machine data in SQL

This file shows how the inputs of production figures (state durations, stop
events, part counts, shifts) are derived from rows of machine data in
PostgreSQL with TimescaleDB, and which mistakes each pattern avoids. The
definitions of the figures are in `oee.md` and `downtime-losses.md`. Table
and column names below are examples (`machine_states`, `part_counter`, time
column `tsp`); use the real ones, written as the place where the SQL runs
requires (schema-qualified in a query over a whole project), and state the
plant's time zone (`Europe/Berlin` here) in every result.

## Shapes of machine data

- **State changes**: a row when the state changes (`tsp, machine_id, state`,
  maybe a reason). A state lasts until the next row of the same machine.
- **Samples**: a row every few seconds or minutes with the current state
  and readings. A row stands for the time until the next one, up to a gap.
- **Counters**: a cumulative part counter, sampled. It resets (shift start,
  power cycle) and may roll over at its maximum.
- **Events**: a row per part (with a result) or per stop (start, end,
  reason).

Before computing, read a sample of the rows and the distinct state values,
and find out which values mean running, which stopped, and which planned.
Never guess what a state or reason code means.

## Durations per state, clipped to a range

```sql
WITH range AS (
  SELECT timestamptz '2026-11-19 06:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-19 14:00 Europe/Berlin') AS t1
),
seed AS (      -- the state in force at t0, looked for up to 7 days back
  SELECT DISTINCT ON (machine_id) machine_id, tsp, state
  FROM machine_states, range
  WHERE tsp < t0 AND tsp >= t0 - interval '7 days'
  ORDER BY machine_id, tsp DESC
),
rows_ AS (
  SELECT machine_id, tsp, state FROM seed
  UNION ALL
  SELECT machine_id, tsp, state FROM machine_states, range
  WHERE tsp >= t0 AND tsp < t1
),
intervals AS ( -- a state lasts until the next row; the last one until t1
  SELECT machine_id, state, greatest(tsp, t0) AS t_start,
         least(coalesce(lead(tsp) OVER (PARTITION BY machine_id ORDER BY tsp), t1),
               t1) AS t_end
  FROM rows_, range
)
SELECT machine_id, state, sum(t_end - t_start) AS duration
FROM intervals WHERE t_end > t_start
GROUP BY machine_id, state;
```

- Without the seed row, the time from t0 to the first row in the range is
  lost, or given to the wrong state. Time before the first known state is
  unknown: report it, do not give it to a state.
- The open last state ends at t1, which is `now()` for a running period.
- **Gaps.** With samples, a row stands for at most about twice the sampling
  interval: add `tsp + interval '10 minutes'` (for 5-minute samples) as a
  third argument of the outer `least()`. Range length minus the summed
  durations is then time without data, reported as such. With state
  changes a gap is invisible: the last state is carried through an outage
  of the logger. Check for gaps in another table of the same device, or
  say the figure assumes none.
- Durations are computed from the intervals, never as count of rows times
  an interval.

## Stops as events

A stop is a run of consecutive intervals in a stop state. Continue the
query above from `intervals`:

```sql
marked AS (
  SELECT *, CASE WHEN state IS DISTINCT FROM lag(state) OVER w THEN 1 ELSE 0 END AS new_run
  FROM intervals WHERE t_end > t_start
  WINDOW w AS (PARTITION BY machine_id ORDER BY t_start)
),
runs AS (
  SELECT *, sum(new_run) OVER (PARTITION BY machine_id ORDER BY t_start) AS run_no
  FROM marked
)
SELECT machine_id, state, min(t_start) AS started, max(t_end) AS ended,
       max(t_end) - min(t_start) AS duration
FROM runs WHERE state = 'STOP'
GROUP BY machine_id, state, run_no;
```

Counting rows in a stop state instead counts every repeated row as a stop.
A reason column joins the same way (take the reason of the run's first row,
or of a reason row that arrives later for the same machine and time).

## Shifts, days and time zones

Shifts come from a calendar in plant time; each interval is split at the
shift bounds. Continue the durations query from `intervals`:

```sql
shifts AS (
  SELECT d::date AS production_day, sh.name,
         (d::date + sh.starts) AT TIME ZONE 'Europe/Berlin'             AS s_start,
         (d::date + sh.starts + sh.length) AT TIME ZONE 'Europe/Berlin' AS s_end
  FROM generate_series(date '2026-11-16', date '2026-11-20', interval '1 day') AS d,
       (VALUES ('early', time '06:00', interval '8 hours'),
               ('late',  time '14:00', interval '8 hours'),
               ('night', time '22:00', interval '8 hours')) AS sh(name, starts, length)
)
SELECT production_day, name, machine_id, state,
       sum(least(t_end, s_end) - greatest(t_start, s_start)) AS duration
FROM intervals JOIN shifts ON t_start < s_end AND t_end > s_start
GROUP BY production_day, name, machine_id, state;
```

- The night shift belongs to the day it starts on here; plants differ, so
  state the rule. A shift crossing midnight is handled by the calendar, not
  by the calendar date of the rows.
- Times are converted in the plant's zone, so the night when clocks change
  has a 7 or 9 hour night shift, as it really does.
- `time_bucket('1 hour', tsp)` and `time_bucket('1 day', tsp, 'Europe/Berlin')`
  are right for hours and plant days (without the zone, days are UTC days).
  Do not use `time_bucket('8 hours', ...)` for shifts: on the night the
  clocks change its buckets no longer start at the shift start.
- `time_bucket` groups rows by their time stamp; it does not split an
  interval. Use it for counts and readings, and the overlap above for
  durations, or a stop from 05:30 to 08:30 lands entirely in one bucket.

## Parts from a counter

```sql
WITH steps AS (
  SELECT machine_id, tsp, counter,
         lag(counter) OVER w AS prev, tsp - lag(tsp) OVER w AS elapsed
  FROM part_counter
  WHERE tsp >= now() - interval '7 days 1 hour'   -- from an hour earlier: the first step has a previous sample
  WINDOW w AS (PARTITION BY machine_id ORDER BY tsp)
)
SELECT machine_id, tsp, elapsed,
       CASE WHEN counter >= prev THEN counter - prev
            -- WHEN prev > 0.9 * 65536 THEN counter + 65536 - prev  -- rollover of a known 16-bit counter
            ELSE counter                                           -- reset to 0: parts since the reset
       END AS parts
FROM steps
WHERE prev IS NOT NULL AND tsp >= now() - interval '7 days';
```

- Never take the maximum minus the minimum over the range: one reset makes
  it wrong. A reset loses the parts between the last sample and the reset;
  say the count may be slightly low.
- Use the rollover line only when the counter's width is known.
- **Plausibility**: a step with more parts than the machine can make in
  `elapsed` (more than about 1.2 x elapsed / ideal cycle time) is a data
  fault, such as one false zero reading, which turns into a huge step. Leave
  it out and report it.
- Each step counts at the time of its later sample; summed by hour or shift
  this is off by at most one sampling interval.

With part events, count rows: `count(*)` and
`count(*) FILTER (WHERE result = 'OK')` per `time_bucket`.

## Putting OEE together

Build one row per machine and shift (or day) with `planned_s`, `run_s`,
`total`, `good` and `ideal_s` (seconds of ideal cycle time times parts),
then:

```sql
SELECT machine_id, production_day, name, planned_s, run_s, total, good,
       run_s / NULLIF(planned_s, 0)       AS availability,
       ideal_s / NULLIF(run_s, 0)         AS performance,
       good::numeric / NULLIF(total, 0)   AS quality,
       CASE WHEN planned_s > 0 AND total = 0 THEN 0
            ELSE run_s / NULLIF(planned_s, 0) * (ideal_s / NULLIF(run_s, 0))
                 * (good::numeric / NULLIF(total, 0)) END AS oee
FROM per_shift;
```

- A missing input stays NULL and makes its part and OEE NULL: "not
  computable". Never `coalesce(..., 1)` or `coalesce(..., 0)` a part.
- `sum()` skips NULLs. With several products, compute
  `CASE WHEN bool_and(ideal_ct_s IS NOT NULL) THEN sum(ideal_ct_s * parts) END`
  so one product without an ideal cycle time makes performance NULL instead
  of silently low. Join the ideal cycle times with a LEFT JOIN, so that such
  a product is not dropped.
- A value the user gave goes into its own CTE with a comment naming its
  source, e.g. `ideal(product, ideal_ct_s) AS (VALUES ('A-100', 2.4))`, and
  into the description of the result.
- Planned time with zero parts counted is OEE 0; no count rows at all is
  NULL. Keep the two apart: build `total` so that "no rows" stays NULL.
- Pooled figures (a line, a week) are sums of these columns divided again,
  never `avg()` of the ratio columns.
