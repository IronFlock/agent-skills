# Production figures from machine data in SQL

This file shows how the inputs of production figures (state durations, stop
events, planned production time, part counts) are derived from rows of
machine data in PostgreSQL with TimescaleDB, and which mistakes each pattern
avoids. The definitions are in `oee.md` and `downtime-losses.md`. Table and
column names are examples (`machine_states`, `part_counter`, time column
`tsp`); use the real ones, written as the place where the SQL runs requires
(schema-qualified in a query over a whole project), and state the plant's
time zone (`Europe/Berlin` here) in every result. Cast to `numeric` before
dividing: integer seconds divided by integer seconds is 0 in PostgreSQL.

## Shapes of machine data

- **State changes**: a row when the state changes (`tsp, machine_id, state`,
  maybe a reason). A state lasts until the next row of the same machine.
- **Samples**: a row every few seconds or minutes with the current state and
  readings. A row stands for the time until the next one, up to a gap.
- **Counters**: a cumulative part counter, sampled. It resets (shift start,
  power cycle, a new batch) and may roll over at its maximum.
- **Events**: a row per part (with a result) or per stop (start, end, reason).

Before computing, read a sample of the rows and the distinct state values, and
find out which values mean running and which a stop. Never guess what a state
or reason code means. Look for duplicates (below).

## The base query: pieces of state

Every later pattern continues this query. `kinds` maps the state values to
`run` or `stop`; an unmapped value (or NULL) becomes `unknown` and is asked
about.

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 06:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-20 06:00 Europe/Berlin') AS t1,
         interval '10 minutes' AS max_gap,    -- samples every 5 minutes; NULL for state changes
         interval '7 days'     AS lookback,   -- longer than any period without production
         interval '1 day'      AS lookahead,  -- how far past t1 a stop's end is read
         interval '2 minutes'  AS micro_stop, -- the plant's threshold: shorter stops are run time
         interval '1 hour'     AS before      -- counter readings before t0 (parts, below)
),
kinds(state, kind) AS (VALUES ('RUN', 'run'), ('FAULT', 'stop'), ('WAIT', 'stop'), ('STOP', 'stop')),
rows_ AS (
  SELECT s.machine_id, s.tsp, s.state, coalesce(k.kind, 'unknown') AS kind
  FROM (SELECT machine_id, tsp, state FROM machine_states, params p
        WHERE tsp >= p.t0 - p.lookback AND tsp < least(p.t1 + p.lookahead, now())) s
  LEFT JOIN kinds k USING (state)
),
ordered AS (    -- equal time stamps: a stop sorts last and keeps the time
  SELECT r.*, lead(r.tsp) OVER w AS next_tsp, row_number() OVER w = 1 AS first_row
  FROM rows_ r
  WINDOW w AS (PARTITION BY r.machine_id ORDER BY r.tsp, r.kind = 'stop', r.state)
),
pieces AS (     -- a row's state until the next row, the end of what was read, or the gap cap
  SELECT * FROM (
    SELECT o.machine_id, o.state, o.kind, o.first_row, o.tsp AS t_start,
           least(coalesce(o.next_tsp, now()), p.t1 + p.lookahead,
                 coalesce(o.tsp + p.max_gap, p.t1 + p.lookahead)) AS t_end,
           o.next_tsp IS NULL AS last_row
    FROM ordered o, params p
  ) x WHERE t_end > t_start
)
SELECT machine_id, kind, sum(least(t_end, p.t1) - greatest(t_start, p.t0)) AS duration
FROM pieces, params p WHERE t_end > p.t0 AND t_start < p.t1
GROUP BY machine_id, kind;
```

- The range minus the summed durations is time without data; report it as
  such. A machine with no row since `t0 - lookback` has only that: a stop
  that began before the lookback becomes no data and drops out of the
  figures, which makes them look better than they are. The lookback must
  exceed the longest period without production (a weekend, holidays, a
  shutdown); say what it is. On state changes, a planned window that starts
  with no data while an older row exists is the sign it was too short (the
  check under "Planned production time").
- Rows are read up to `lookahead` past t1, so that a stop crossing t1 is
  judged by its whole length; every figure of the range is clipped at t1.
- **Gaps.** With samples, a row stands for at most `max_gap` (about twice the
  sampling interval). With state changes a gap is invisible: the last state
  is carried through an outage of the logger. Check another table of the same
  device, or say the figure assumes no outage.
- Durations come from pieces, never from a count of rows times an interval.

**In a transform** keep the read bounded as above: it runs on every refresh.
For a one-off question about a machine silent for longer than the lookback,
read the last row before it however old, and add it to the rows:

```sql
older AS (      -- one-off questions only: reads the whole history before the lookback
  SELECT DISTINCT ON (s.machine_id) s.machine_id, s.tsp, s.state
  FROM machine_states s, params p
  WHERE s.tsp < p.t0 - p.lookback
  ORDER BY s.machine_id, s.tsp DESC
),
```

with `UNION ALL SELECT machine_id, tsp, state FROM older` inside the subquery
of `rows_`. A per-machine lookup (`CROSS JOIN LATERAL (... WHERE s.machine_id
= m.machine_id ORDER BY s.tsp DESC LIMIT 1)` over a list of machines) is cheap
only with an index on `(machine_id, tsp)`; an entity table's key index is
one, a plain time series usually has only an index on `tsp`. Check before you
rely on it.

## Duplicates

```sql
SELECT machine_id, tsp, array_agg(state ORDER BY state) AS states
FROM machine_states
WHERE tsp >= now() - interval '7 days'
GROUP BY machine_id, tsp HAVING count(DISTINCT state) > 1;
```

Two states at one time stamp are a finding: list them. The base query then
gives the time to the stop (it sorts last), so a stop never vanishes; say so.

## Stops as events

A stop is a run of pieces in a stop state, with no gap between them: FAULT
followed by WAIT is one stop, and a gap in the data ends a stop. Continue
the base query from `pieces`:

```sql
marked AS (
  SELECT *, CASE WHEN kind = 'stop' AND lag(kind) OVER w = 'stop' AND lag(t_end) OVER w = t_start
                 THEN 0 ELSE 1 END AS new_event
  FROM pieces WINDOW w AS (PARTITION BY machine_id ORDER BY t_start)
),
numbered AS (
  SELECT *, sum(new_event) OVER (PARTITION BY machine_id ORDER BY t_start) AS event_no FROM marked
),
stops AS (
  SELECT n.machine_id, n.event_no,
         min(n.t_start) AS started,                  -- the true start, also before t0
         bool_or(n.first_row) AS may_have_started_earlier,
         max(n.t_end) AS ended,
         sum(n.t_end - n.t_start) AS length,         -- the whole stop, past t1 too; never a gap
         bool_or(n.last_row) AS end_not_seen,        -- ongoing if t1 is now, else at least this long
         sum(least(n.t_end, p.t1) - greatest(n.t_start, p.t0))
           FILTER (WHERE n.t_end > p.t0 AND n.t_start < p.t1) AS in_range,
         (array_agg(n.state ORDER BY n.t_start))[1] AS first_state
  FROM numbered n, params p WHERE n.kind = 'stop'
  GROUP BY n.machine_id, n.event_no
)
SELECT s.*, s.length < p.micro_stop AND NOT s.end_not_seen AS micro_stop,
       s.started >= p.t0 AS counted_in_range   -- a stop counts once, in the period it began in
FROM stops s, params p
WHERE s.ended > p.t0 AND s.started < p.t1;
```

- A stop that began before the range shows its true start, gives the range
  only its minutes inside it, and is counted in the period it began in.
- A stop is a micro-stop by its whole length, read past t1; one whose end was
  not seen is never a micro-stop (ongoing, or longer than the lookahead).
- All its minutes go to `first_state` (or the reason of its first row). That
  is a convention; say so. The alternative: minutes per state of each piece,
  with the stop counted under its first reason.

## Planned production time

Shifts and the planned stops in them come from the plant, as a calendar in
plant time: each shift a `+1` row, each break inside it a `-1` row (offset
from the shift start, so a break after midnight belongs to its night shift).
Shifts must not overlap, and every break must lie inside its shift: run the
check below first. Run time, stops and parts are clipped to these windows,
so a machine that runs through a break gains neither run time nor parts from
it. Continue the query from `stops`:

```sql
classified AS (
  SELECT n.*, coalesce(s.length < p.micro_stop AND NOT s.end_not_seen, false) AS micro
  FROM numbered n LEFT JOIN stops s USING (machine_id, event_no), params p
),
calendar AS (
  SELECT d::date AS production_day, c.shift, c.sign,
         (d::date + c.shift_start + c.offset_) AT TIME ZONE 'Europe/Berlin'            AS w_start,
         (d::date + c.shift_start + c.offset_ + c.length) AT TIME ZONE 'Europe/Berlin' AS w_end
  FROM generate_series(date '2026-11-19', date '2026-11-19', interval '1 day') AS d,
       (VALUES ('early', time '06:00', interval '0 hours',   interval '8 hours',    1),
               ('early', time '06:00', interval '4 hours',   interval '30 minutes', -1),
               ('late',  time '14:00', interval '0 hours',   interval '8 hours',    1),
               ('late',  time '14:00', interval '4 hours',   interval '30 minutes', -1),
               ('night', time '22:00', interval '0 hours',   interval '8 hours',    1),
               ('night', time '22:00', interval '4 hours',   interval '30 minutes', -1))
         AS c(shift, shift_start, offset_, length, sign)
),
planned AS (    -- planned production time so far (a running shift counts up to t1)
  SELECT production_day, shift,
         sum(c.sign * extract(epoch FROM least(c.w_end, p.t1) - c.w_start)) AS planned_s
  FROM calendar c, params p WHERE c.w_start < p.t1
  GROUP BY production_day, shift
),
split AS (
  SELECT c.production_day, c.shift, x.machine_id,
         CASE WHEN x.kind = 'run' OR x.micro THEN 'run' ELSE x.kind END AS kind,
         c.sign * extract(epoch FROM least(x.t_end, c.w_end, p.t1) - greatest(x.t_start, c.w_start)) AS s
  FROM classified x JOIN calendar c ON x.t_start < c.w_end AND x.t_end > c.w_start, params p
  WHERE least(x.t_end, c.w_end, p.t1) > greatest(x.t_start, c.w_start)   -- only overlaps before t1
)
SELECT p.production_day, p.shift, m.machine_id, p.planned_s,
       coalesce(sum(s.s) FILTER (WHERE s.kind = 'run'), 0)  AS run_s,
       coalesce(sum(s.s) FILTER (WHERE s.kind = 'stop'), 0) AS stop_s,
       coalesce(sum(s.s) FILTER (WHERE s.kind = 'unknown'), 0) AS unknown_s,
       p.planned_s - coalesce(sum(s.s), 0) AS no_data_s
FROM planned p CROSS JOIN (SELECT DISTINCT machine_id FROM pieces) m
LEFT JOIN split s ON s.production_day = p.production_day AND s.shift = p.shift AND s.machine_id = m.machine_id
GROUP BY p.production_day, p.shift, m.machine_id, p.planned_s;
```

- Let t0 and t1 cover the calendar's windows: the windows set the period.
- Run + stop + unknown + no data = planned time, by construction. The
  figures are computed over run + stop, the planned time with usable state
  data (below); unknown and no data are reported beside them.
- When the data records planned stops as a state, ask whether the plan
  should come from those pieces instead of fixed times, and say which.
- Parts are clipped the same way: `sum(c.sign * parts)` over counter steps
  (below) joined on `step.tsp > c.w_start AND step.tsp <= c.w_end`. Parts
  counted while the state is unknown or missing are kept out of total and
  good, and reported apart.
- The night shift belongs to the day it starts on here; plants differ, so
  state the rule. Converting in the plant's zone makes the night the clocks
  change 7 or 9 hours long, as it really is.
- `time_bucket('1 hour', tsp, 'Europe/Berlin')` and `time_bucket('1 day',
  tsp, 'Europe/Berlin')` give plant hours and days (without the zone, hours
  are wrong in zones with a half-hour offset and days are UTC days; on the
  night the clocks go back both 2 o'clock hours fall into one bucket). Never
  `time_bucket('8 hours', ...)` for shifts: on the night the clocks change
  its buckets stop starting at the shift start. `time_bucket` groups rows by
  their time stamp and does not split an interval: use it for counts and
  readings, and the overlap above for durations.

Check the calendar (continue from `calendar`); any row means the figures
cannot be trusted until the plan is corrected:

```sql
SELECT 'windows overlap' AS problem, a.production_day, a.shift, a.w_start, b.shift AS other
FROM calendar a JOIN calendar b
  ON a.sign = b.sign AND a.w_start < b.w_end AND b.w_start < a.w_end
 AND (a.production_day, a.shift, a.w_start) < (b.production_day, b.shift, b.w_start)
UNION ALL
SELECT 'break outside its shift', k.production_day, k.shift, k.w_start, NULL
FROM calendar k
WHERE k.sign = -1 AND NOT EXISTS (
  SELECT 1 FROM calendar s
  WHERE s.sign = 1 AND s.production_day = k.production_day AND s.shift = k.shift
    AND k.w_start >= s.w_start AND k.w_end <= s.w_end);
```

Run time outside the planned windows (unscheduled overtime, running through
a break, a wrong plan), reported apart (continue from `split`):

```sql
SELECT r.machine_id, r.run_s - coalesce(w.run_s, 0) AS run_outside_plan_s
FROM (SELECT x.machine_id,
             sum(extract(epoch FROM least(x.t_end, p.t1) - greatest(x.t_start, p.t0))) AS run_s
      FROM classified x, params p
      WHERE (x.kind = 'run' OR x.micro) AND x.t_end > p.t0 AND x.t_start < p.t1
      GROUP BY x.machine_id) r
LEFT JOIN (SELECT machine_id, sum(s) AS run_s FROM split WHERE kind = 'run' GROUP BY machine_id) w
  USING (machine_id);
```

On state changes (`max_gap` NULL), a planned window that begins with no data
while an older row exists means the lookback was too short; raise it and run
again (continue from `split`):

```sql
SELECT m.machine_id, min(c.w_start) AS first_window_without_state
FROM (SELECT DISTINCT machine_id FROM pieces) m, calendar c, params p
WHERE p.max_gap IS NULL AND c.sign = 1 AND c.w_start >= p.t0 AND c.w_start < p.t1
  AND NOT EXISTS (SELECT 1 FROM pieces x WHERE x.machine_id = m.machine_id
                  AND x.t_start <= c.w_start AND x.t_end > c.w_start)
  AND EXISTS (SELECT 1 FROM machine_states s WHERE s.machine_id = m.machine_id
              AND s.tsp < p.t0 - p.lookback)
GROUP BY m.machine_id;
```

## Parts from a counter

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 06:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-20 06:00 Europe/Berlin') AS t1,
         interval '1 hour' AS before                -- to have the reading before t0
),
readings AS (   -- NULL readings ignored; equal time stamps: the lowest reading
  SELECT DISTINCT ON (c.machine_id, c.tsp) c.machine_id, c.tsp, c.counter
  FROM part_counter c, params p
  WHERE c.counter IS NOT NULL AND c.tsp >= p.t0 - p.before AND c.tsp < p.t1
  ORDER BY c.machine_id, c.tsp, c.counter
),
steps AS (
  SELECT machine_id, tsp, counter, lag(counter) OVER w AS prev,
         extract(epoch FROM tsp - lag(tsp) OVER w) AS elapsed_s
  FROM readings WINDOW w AS (PARTITION BY machine_id ORDER BY tsp)
),
step_kinds AS (
  SELECT s.*, CASE WHEN s.counter >= s.prev THEN 'count'
                   -- WHEN s.prev > 0.9 * 65536 THEN 'rollover'  -- only for a counter of known width
                   WHEN s.prev - s.counter < 1 THEN 'jitter'      -- less than one part
                   WHEN s.counter < 0.5 * s.prev THEN 'reset'     -- fell to near its start
                   ELSE 'decrease' END AS kind                    -- a correction, or a reset
  FROM steps s, params p WHERE s.prev IS NOT NULL AND s.tsp >= p.t0
),
usual AS (      -- the usual counting rate, from the steps that counted
  SELECT machine_id, count(*) AS n,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY (counter - prev) / elapsed_s) AS rate
  FROM step_kinds WHERE kind = 'count' AND counter > prev AND elapsed_s > 0
  GROUP BY machine_id
),
judged AS (
  SELECT k.*, CASE WHEN k.kind = 'count' AND u.n >= 10
                    AND k.counter - k.prev > 10 * u.rate * k.elapsed_s THEN 'implausible'
                   ELSE k.kind END AS verdict,
         coalesce(u.n, 0) >= 10 AS plausibility_checked
  FROM step_kinds k LEFT JOIN usual u USING (machine_id)
)
SELECT machine_id, tsp, prev, counter, verdict, plausibility_checked,
       CASE verdict WHEN 'count' THEN counter - prev
                    WHEN 'rollover' THEN counter + 65536 - prev ELSE 0 END AS parts_low,
       CASE verdict WHEN 'count' THEN counter - prev
                    WHEN 'rollover' THEN counter + 65536 - prev
                    WHEN 'implausible' THEN counter - prev
                    WHEN 'jitter' THEN 0
                    ELSE counter END AS parts_high
FROM judged;
```

- No rule tells every reset, correction and burst apart, so every doubtful
  step is flagged and counted both ways: `parts_low` without it, `parts_high`
  with it (a reset or a decrease as a reset to 0, an implausible step as
  counted). Sum both. When they agree, report one figure. When they differ,
  report the range, list the flagged steps with their time and readings, and
  ask what happened (a reset, an operator's correction, a tray counted at
  once); never pick one silently.
- `jitter` (a fall of less than one part, a float counter's noise) counts no
  parts. A step is `implausible` above ten times the median rate, judged once
  a machine has ten counting steps; with fewer the check cannot run
  (`plausibility_checked`), say so. Where the ideal cycle time is known, a
  step above about 1.2 x elapsed / ideal cycle time is doubtful as well.
- After a reset to a preset value the true number of parts cannot be known
  from the data; ask for the preset.
- Never take the maximum minus the minimum over the range: one reset makes it
  wrong. Use the rollover line only when the counter's width is known.
- Each step counts at the time of its later reading; summed by hour or shift
  this is off by at most one reading interval.

Parts per planned window, kept only where the state is known: continue the
planned query with the CTEs above from `readings` to `judged`, then

```sql
placed AS (     -- each step at its later reading: its window, and whether the state was known
  SELECT c.production_day, c.shift, c.sign, j.*,
         EXISTS (SELECT 1 FROM classified x
                 WHERE x.machine_id = j.machine_id AND x.kind IN ('run', 'stop')
                   AND j.tsp > x.t_start AND j.tsp <= x.t_end) AS state_known
  FROM judged j JOIN calendar c ON j.tsp > c.w_start AND j.tsp <= c.w_end
)
SELECT production_day, shift, machine_id,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev
                               WHEN 'rollover' THEN counter + 65536 - prev ELSE 0 END)
         FILTER (WHERE state_known) AS parts_low,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev
                               WHEN 'rollover' THEN counter + 65536 - prev
                               WHEN 'implausible' THEN counter - prev
                               WHEN 'jitter' THEN 0 ELSE counter END)
         FILTER (WHERE state_known) AS parts_high,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev ELSE 0 END)
         FILTER (WHERE NOT state_known) AS parts_left_out
FROM placed GROUP BY production_day, shift, machine_id;
```

Parts made while the state is unknown or missing are not set against run
time; report `parts_left_out` apart. With part events, count rows the same
way: `count(*)` and `count(*) FILTER (WHERE result = 'OK')` per window and
known state.

## Putting OEE together

One row per machine and shift with `planned_s`, `run_s`, `stop_s` (above),
`total` and `good` counts, `ideal_s` (the sum of ideal cycle time x parts, per
product) and `ideal_good_s` (the same for good parts). An input the user gave
(an ideal cycle time, a shift plan) is named with its source in the
transform's description: a comment inside the SQL is not kept in a stored view.

```sql
WITH counted AS (   -- without run time, no count rows mean zero parts: a known zero
  SELECT machine_id, production_day, shift, planned_s, run_s, stop_s,
         planned_s - run_s - stop_s AS left_out_s,       -- unknown state and no data
         CASE WHEN run_s = 0 THEN coalesce(total, 0) ELSE total END AS total,
         CASE WHEN run_s = 0 THEN coalesce(good, 0) ELSE good END AS good,
         CASE WHEN run_s = 0 THEN coalesce(ideal_s, 0) ELSE ideal_s END AS ideal_s,
         CASE WHEN run_s = 0 THEN coalesce(ideal_good_s, 0) ELSE ideal_good_s END AS ideal_good_s
  FROM per_shift
  WHERE run_s + stop_s > 0     -- no usable state data: left out, listed as "no data"
)
SELECT machine_id, production_day, shift, planned_s, left_out_s, total, good,
       run_s::numeric / NULLIF(run_s + stop_s, 0)        AS availability,
       ideal_s::numeric / NULLIF(run_s, 0)               AS performance,
       coalesce(ideal_good_s::numeric / NULLIF(ideal_s, 0),
                good::numeric / NULLIF(total, 0))        AS quality,
       ideal_good_s IS NULL AND total IS NOT NULL        AS quality_by_count,
       good::numeric / NULLIF(total, 0)                  AS good_ratio,
       ideal_good_s::numeric / NULLIF(run_s + stop_s, 0) AS oee
FROM counted;
```

- Every part and OEE are computed over run + stop, the planned time with
  usable state data, so availability x performance x quality = `oee` exactly.
  `left_out_s` (unknown state and no data) is reported beside the figures; a
  large share makes them not representative.
- Quality weights each part by its ideal cycle time; for one product it
  equals `good_ratio` (good / total), which may be shown beside it. Without
  ideal cycle times it falls back to `good_ratio`, with `quality_by_count`
  true: say it is quality by count.
- A missing input stays NULL and makes its part and OEE NULL: "not
  computable". Never `coalesce(..., 1)` a part. With run time but no count
  rows, the counts are missing, not zero. Build `ideal_s` with
  `CASE WHEN bool_and(ideal_ct_s IS NOT NULL) THEN sum(ideal_ct_s * parts) END`
  over the products, joined with a LEFT JOIN, so one product without an ideal
  cycle time makes it NULL instead of silently low.

Pooled over machines or shifts (a line, a day): continue from `counted`,
sums divided again, each guarded so that one missing input makes the pooled
part NULL:

```sql
SELECT CASE WHEN bool_and(run_s IS NOT NULL AND stop_s IS NOT NULL)
            THEN sum(run_s)::numeric / NULLIF(sum(run_s + stop_s), 0) END AS availability,
       CASE WHEN bool_and(ideal_s IS NOT NULL)
            THEN sum(ideal_s)::numeric / NULLIF(sum(run_s), 0) END AS performance,
       coalesce(CASE WHEN bool_and(ideal_good_s IS NOT NULL AND ideal_s IS NOT NULL)
                     THEN sum(ideal_good_s)::numeric / NULLIF(sum(ideal_s), 0) END,
                CASE WHEN bool_and(total IS NOT NULL)
                     THEN sum(good)::numeric / NULLIF(sum(total), 0) END) AS quality,
       NOT bool_and(ideal_good_s IS NOT NULL AND ideal_s IS NOT NULL) AS quality_by_count,
       CASE WHEN bool_and(ideal_good_s IS NOT NULL)
            THEN sum(ideal_good_s)::numeric / NULLIF(sum(run_s + stop_s), 0) END AS oee,
       sum(left_out_s) AS left_out_s
FROM counted;
```

Pooled quality by count (`quality_by_count`) is valid only when all rows
are one product, or products of equal ideal cycle time; say so, or leave it
out. A machine-shift left out for lack of state data is listed: as "state
values not mapped" when its time is unknown state (the fix is the mapping in
`kinds`), else as "no data". Never `avg()` a ratio column.
