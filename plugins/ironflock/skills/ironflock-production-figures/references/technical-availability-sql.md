# Technical availability from machine data in SQL

This file computes technical availability (`technical-availability.md`)
from stop rows in PostgreSQL with TimescaleDB, in the style and on the
conventions of `machine-data-sql.md`: table and column names are examples,
the time zone is stated, and ratios are cast to `numeric`.

## Input

- **Stops**: one row per stop or alarm, `machine_stops(machine_id, started,
  ended, reason)`, `ended` NULL while it is open. Alarms may overlap. An
  alarm that does not stop the machine (a warning, a message) is mapped to
  `no_stop` and left out; an unmapped one counts as an unknown stop.
- **Mapping**: reason code, alarm number or alarm class to `technical`,
  `organisational`, `maintenance`, `test`, `consequential` or `no_stop`, as
  agreed. Anything else is `unknown`.
- **Occupied time**: windows per machine from the user's plan or the
  contract, each in its customer's time zone and labelled with its `period`
  (the day or month in that zone, so that the labels of all customers
  match). The windows set the periods and the read: one result row per
  machine and period. A stop counts once, in the period of its first
  occupied minute, and only listed windows are known: generate the windows
  from the plan for every period back to the earliest stop read, also in a
  monthly transform, or a stop that crosses into the next period, or an
  alarm open for weeks, is counted again. Windows must not overlap: a minute
  in two windows counts once, for the period whose label sorts first, and
  the window check below lists them for the user. Never read them from when the machine
  ran.
- **Outages**: time without data, from a heartbeat or the state path. A stop
  table alone cannot show them: time without a stop row counts as running.
- **Start and end of a stop** are those of its row. When the contract counts
  from the report to the supplier, or only in the supplier's working hours,
  or until the hand-back, cut the rows to that first.

## Times per category and the figure

The time is cut at every boundary of a stop, an outage and a window. Each
piece inside an occupied window goes to one owner: an outage first, else
the stop that began first (at the same start the technical one, then the
shorter), else running. So overlapping and duplicate stops count each
minute once.

```sql
WITH choices AS (    -- the agreed definition
  SELECT false AS maintenance_apart,   -- true: maintenance taken out of the base
         false AS test_is_use          -- true: test time counts as utilisation
),
categories(reason, category) AS (VALUES
  ('E101', 'technical'), ('E205', 'technical'), ('E300', 'technical'),
  ('NO_MAT', 'organisational'), ('NO_STAFF', 'organisational'), ('PM', 'maintenance'),
  ('TRIAL', 'test'), ('STARVED', 'consequential'), ('W17', 'no_stop')),
occupied(machine_id, w_start, w_end, period) AS (VALUES
  ('M1', timestamptz '2026-11-16 06:00 Europe/Berlin', timestamptz '2026-11-16 22:00 Europe/Berlin', '2026-11-16'),
  ('M2', timestamptz '2026-11-16 06:00 Europe/Berlin', timestamptz '2026-11-16 14:00 Europe/Berlin', '2026-11-16'),
  ('M3', timestamptz '2026-11-16 06:00 Europe/Berlin', timestamptz '2026-11-16 10:00 Europe/Berlin', '2026-11-16'),
  ('M3', timestamptz '2026-11-16 18:00 Europe/Berlin', timestamptz '2026-11-16 22:00 Europe/Berlin', '2026-11-16')),
params AS (     -- the read follows the windows
  SELECT min(w_start) AS t0, least(now(), max(w_end)) AS t1,
         interval '31 days' AS lookback          -- for the guard below
  FROM occupied
),
outages(machine_id, g_start, g_end) AS (VALUES
  ('M3', timestamptz '2026-11-16 20:00 Europe/Berlin', timestamptz '2026-11-16 20:30 Europe/Berlin')),
stops AS (      -- exact duplicates collapse; an open stop lasts until t1
  SELECT DISTINCT s.machine_id, s.started, coalesce(s.ended, p.t1) AS ended,
         s.ended IS NULL AS open, s.reason, coalesce(c.category, 'unknown') AS category
  FROM machine_stops s CROSS JOIN params p
  LEFT JOIN categories c ON c.reason = s.reason
  WHERE s.started < (SELECT t1 FROM params)
    AND (s.ended > (SELECT t0 FROM params) OR s.ended IS NULL)
    AND (s.ended IS NULL OR s.ended > s.started)
    AND c.category IS DISTINCT FROM 'no_stop'
),
spans AS (
  SELECT machine_id, g_start AS started, g_end AS ended, 'no_data' AS category, 0 AS rank FROM outages
  UNION ALL
  SELECT machine_id, started, ended, category, 1 FROM stops
),
cuts AS (       -- every boundary, clipped to the read
  SELECT DISTINCT b.machine_id, greatest(least(b.t, p.t1), p.t0) AS t
  FROM (SELECT machine_id, started AS t FROM spans UNION ALL SELECT machine_id, ended FROM spans
        UNION ALL SELECT machine_id, w_start FROM occupied UNION ALL SELECT machine_id, w_end FROM occupied) b,
       params p
),
slices AS (
  SELECT machine_id, t AS s_start, lead(t) OVER (PARTITION BY machine_id ORDER BY t) AS s_end FROM cuts
),
owned AS (      -- each occupied piece to its period and one owner
  SELECT DISTINCT ON (sl.machine_id, sl.s_start) sl.machine_id, o.period, extract(epoch FROM sl.s_end - sl.s_start) AS secs,
         coalesce((SELECT x.category FROM spans x
                   WHERE x.machine_id = sl.machine_id AND x.started <= sl.s_start AND x.ended >= sl.s_end
                   ORDER BY x.rank, x.started, x.category <> 'technical', x.ended   -- technical first: x.rank, x.category <> 'technical', x.started, x.ended
                   LIMIT 1), 'running') AS category,
         EXISTS (SELECT 1 FROM spans x
                 WHERE x.machine_id = sl.machine_id AND x.category = 'technical'
                   AND x.started <= sl.s_start AND x.ended >= sl.s_end) AS technical_active
  FROM slices sl
  JOIN occupied o ON o.machine_id = sl.machine_id AND o.w_start <= sl.s_start AND o.w_end >= sl.s_end
  WHERE sl.s_end > sl.s_start
  ORDER BY sl.machine_id, sl.s_start, o.period     -- a minute in two windows counts once
),
times AS (
  SELECT machine_id, period, sum(secs) AS occupied_s,
         coalesce(sum(secs) FILTER (WHERE category = 'no_data'), 0)        AS no_data_s,
         coalesce(sum(secs) FILTER (WHERE category = 'running'), 0)        AS utilisation_s,
         coalesce(sum(secs) FILTER (WHERE category = 'technical'), 0)      AS technical_s,
         coalesce(sum(secs) FILTER (WHERE category = 'organisational'), 0) AS organisational_s,
         coalesce(sum(secs) FILTER (WHERE category = 'maintenance'), 0)    AS maintenance_s,
         coalesce(sum(secs) FILTER (WHERE category = 'test'), 0)           AS test_s,
         coalesce(sum(secs) FILTER (WHERE category = 'consequential'), 0)  AS consequential_s,
         coalesce(sum(secs) FILTER (WHERE category = 'unknown'), 0)        AS unknown_s,
         coalesce(sum(secs) FILTER (WHERE technical_active AND category <> 'technical'), 0) AS technical_elsewhere_s
  FROM owned GROUP BY machine_id, period
),
placed AS (     -- each stop in the period of its first occupied minute
  SELECT DISTINCT ON (s.machine_id, s.started, s.ended, s.reason) s.*, o.period,
         greatest(s.started, o.w_start) < p.t1 AS counted
  FROM stops s JOIN occupied o ON o.machine_id = s.machine_id
   AND o.w_start < s.ended AND o.w_end > s.started, params p
  ORDER BY s.machine_id, s.started, s.ended, s.reason, greatest(s.started, o.w_start), o.period
),
stop_counts AS (
  SELECT machine_id, period, count(*) AS stops,
         count(*) FILTER (WHERE category = 'technical') AS technical_stops,
         count(*) FILTER (WHERE category = 'unknown')   AS stops_without_reason
  FROM placed WHERE counted GROUP BY machine_id, period
),
reached AS (    -- each stop in every period it reaches
  SELECT machine_id, period,
         count(*) FILTER (WHERE open)                 AS open_stops,
         min(started) FILTER (WHERE open)             AS open_since,
         count(*) FILTER (WHERE category <> 'unknown') AS reached_with_reason
  FROM (SELECT DISTINCT s.*, o.period FROM stops s JOIN occupied o ON o.machine_id = s.machine_id
         AND o.w_start < s.ended AND o.w_end > s.started) r
  GROUP BY machine_id, period
),
figures AS (
  SELECT t.*, t.occupied_s - t.no_data_s AS known_s,
         t.occupied_s - t.no_data_s - CASE WHEN ch.maintenance_apart THEN t.maintenance_s ELSE 0 END AS base_s,
         coalesce(n.stops, 0) AS stops, coalesce(n.technical_stops, 0) AS technical_stops,
         coalesce(n.stops_without_reason, 0) AS stops_without_reason,
         coalesce(r.open_stops, 0) AS open_stops, r.open_since,
         t.unknown_s > 0 AND coalesce(r.reached_with_reason, 0) = 0 AS no_stop_has_a_reason
  FROM times t LEFT JOIN stop_counts n USING (machine_id, period)
  LEFT JOIN reached r USING (machine_id, period), choices ch
),
result AS (
  SELECT f.*,
         CASE WHEN unknown_s = 0 THEN 1 - technical_s::numeric / NULLIF(base_s, 0) END AS technical_availability,
         CASE WHEN NOT no_stop_has_a_reason
              THEN 1 - (technical_s + unknown_s)::numeric / NULLIF(base_s, 0) END   AS availability_low,
         CASE WHEN NOT no_stop_has_a_reason
              THEN 1 - technical_s::numeric / NULLIF(base_s, 0) END                 AS availability_high,
         (utilisation_s + CASE WHEN ch.test_is_use THEN test_s ELSE 0 END)::numeric
           / NULLIF(known_s, 0)                                                     AS total_utilisation
  FROM figures f, choices ch
)
SELECT * FROM result;
```

- `base_s` is the base of every ratio: occupied time with data, without
  maintenance when that is agreed. Report `no_data_s` beside it, list the
  outages and ask what happened in them: a fault that cuts the logger's
  power leaves the base instead of lowering the figure.
- `technical_availability` is set only when every stop minute has a
  category; otherwise report `availability_low` to `availability_high` with
  `stops_without_reason` and `unknown_s`. When `no_stop_has_a_reason`, all
  three are NULL: not computable.
- `technical_elsewhere_s`: minutes a technical stop was active while
  another stop or an outage owned them. It shows what the owner rule moves;
  report it when it is not 0. "Technical first" is the ORDER BY of the
  comment.
- Over consecutive periods `stops` and the minutes add up to the totals.
  `open_stops` lists every open stop that reaches a period, `open_since`
  its start: an alarm open for weeks is usually a lost end row; ask.
- A machine with a window but no stop rows shows as running; that is right
  only if it sent data.

**In a transform**, `stops` reads only rows that start before t1 and end
after t0 or are open: an index on `(machine_id, ended)` serves it. On a
table partitioned by `started`, add
`s.started >= (SELECT t0 - lookback FROM params)` and run this guard
(replace the last line); any row means the lookback is too short:

```sql
SELECT machine_id, started, reason FROM machine_stops, params p
WHERE started < p.t0 - p.lookback AND (ended > p.t0 OR ended IS NULL);
```

## From states instead of stop rows

With state changes or samples, take the base query of `machine-data-sql.md`
up to `pieces` (its `kinds` maps every stop state to `stop`; set its t0 to
the first window's start and t1 to the last window's end), continue with
the query above without its `params` and `outages`, and put these after
`occupied`. Never use its `stops` pattern here: it gives a whole stop the
reason of its first row, so FAULT then NO_MAT would count as technical
throughout. The reason is the state value. A machine that writes one
generic stop state and its reasons as alarm codes elsewhere is not covered:
its stops all come out unknown. Use the alarm rows as stops instead (above),
or ask for a state per reason.

```sql
runs AS (       -- one row per run of equal state; a change or a gap starts a new one
  SELECT x.*, sum(x.new_run) OVER (PARTITION BY x.machine_id ORDER BY x.t_start) AS run_no
  FROM (SELECT pc.*, CASE WHEN lag(pc.state) OVER w = pc.state AND lag(pc.t_end) OVER w = pc.t_start
                          THEN 0 ELSE 1 END AS new_run
        FROM pieces pc WHERE pc.kind = 'stop'
        WINDOW w AS (PARTITION BY pc.machine_id ORDER BY pc.t_start)) x
),
machine_stops AS (
  SELECT machine_id, min(t_start) AS started,
         CASE WHEN bool_or(last_row) THEN NULL ELSE max(t_end) END AS ended, state AS reason
  FROM runs GROUP BY machine_id, run_no, state
),
edges AS (      -- time with usable state, and the ends of the read
  SELECT machine_id, t_start, t_end FROM pieces WHERE kind <> 'unknown'
  UNION ALL SELECT DISTINCT o.machine_id, p.t0, p.t0 FROM occupied o, params p
  UNION ALL SELECT DISTINCT o.machine_id, p.t1, p.t1 FROM occupied o, params p
),
outages AS (    -- no data, and unmapped states
  SELECT machine_id, g_start, g_end FROM (
    SELECT machine_id, t_start AS g_end,
           max(t_end) OVER (PARTITION BY machine_id ORDER BY t_start, t_end
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS g_start
    FROM edges) e
  WHERE g_end > g_start
),
```

There, check first that the read covers the windows (replace the last
line); any row loses minutes and stops:

```sql
SELECT o.* FROM occupied o, params p
WHERE o.w_start < p.t0 OR (o.w_end > p.t1 AND p.t1 < now());
```

## Checks before reporting

Replace the last line of the query with one of these.

Overlapping windows, a fault of the plan to show the user:

```sql
SELECT a.machine_id, a.period, a.w_start, a.w_end,
       b.period AS other_period, b.w_start AS other_start, b.w_end AS other_end
FROM occupied a JOIN occupied b
  ON a.machine_id = b.machine_id AND a.w_start < b.w_end AND b.w_start < a.w_end
 AND (a.w_start, a.w_end, a.period) < (b.w_start, b.w_end, b.period);
```

Codes without a category, to be mapped by the builder and the user:

```sql
SELECT machine_id, reason, count(*) AS stops,
       sum(extract(epoch FROM least(ended, (SELECT t1 FROM params))
                            - greatest(started, (SELECT t0 FROM params)))) AS seconds_read
FROM stops WHERE category = 'unknown'
GROUP BY machine_id, reason ORDER BY stops DESC;
```

Overlapping stops of different categories, the doubtful cases for both
sides to decide:

```sql
SELECT a.machine_id, a.reason, a.started, a.ended, b.reason AS other_reason,
       b.started AS other_started, b.ended AS other_ended
FROM stops a JOIN stops b
  ON a.machine_id = b.machine_id AND a.category <> b.category
 AND a.started < b.ended AND b.started < a.ended
 AND (a.started, a.ended, coalesce(a.reason, '')) < (b.started, b.ended, coalesce(b.reason, ''));
```

Rows left out or collapsed (an end before its start, exact duplicates):

```sql
SELECT machine_id, started, ended, reason, count(*) AS copies,
       bool_or(ended <= started) AS end_not_after_start
FROM machine_stops, params p
WHERE started < p.t1 AND (ended > p.t0 OR ended IS NULL OR ended <= started)
GROUP BY machine_id, started, ended, reason
HAVING count(*) > 1 OR bool_or(ended <= started);
```

## Pooled over machines of one type

Per period, sums divided again on the same base; machines without reasons
or without data are left out of every figure and named:

```sql
SELECT period, count(*) FILTER (WHERE usable) AS machines,
       string_agg(machine_id, ', ') FILTER (WHERE no_stop_has_a_reason) AS left_out_no_reasons,
       string_agg(machine_id, ', ') FILTER (WHERE NOT usable AND NOT no_stop_has_a_reason) AS left_out_no_data,
       sum(base_s) FILTER (WHERE usable) AS base_s,
       sum(technical_s) FILTER (WHERE usable) AS technical_s,
       sum(unknown_s) FILTER (WHERE usable) AS unknown_s,
       1 - (sum(technical_s + unknown_s) FILTER (WHERE usable))::numeric
         / NULLIF(sum(base_s) FILTER (WHERE usable), 0) AS availability_low,
       1 - (sum(technical_s) FILTER (WHERE usable))::numeric
         / NULLIF(sum(base_s) FILTER (WHERE usable), 0) AS availability_high,
       (sum(utilisation_s + CASE WHEN test_is_use THEN test_s ELSE 0 END) FILTER (WHERE usable))::numeric
         / NULLIF(sum(known_s) FILTER (WHERE usable), 0) AS total_utilisation
FROM (SELECT r.*, ch.test_is_use, NOT r.no_stop_has_a_reason AND r.base_s > 0 AS usable
      FROM result r, choices ch) x
GROUP BY period ORDER BY period;
```

Never `avg(technical_availability)`. A machine with no row in `result` has
no occupied time in the period; list it as such.
