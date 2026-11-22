# Failure and repair figures from machine data in SQL

This file shows how failures, the operating time between them and their
restoration times are derived from state rows, stop reasons and alarms in
PostgreSQL, continuing the base query of `machine-data-sql.md` (same
`params`, `kinds` and `pieces`; read it first). The definitions and when each
figure means something are in `maintenance-reliability.md`. Table, column,
state and code values are examples: use the real ones, and take what each
state, reason and alarm code means from the column descriptions or the user,
never from a guess.

## Pieces with a reliability class

Carry the stop reason through the base query: `reason` in the subquery of
`rows_` and `s.reason` in its select list, `o.reason` in `pieces` (without a
reason column, `NULL::text AS reason`), and map every state in `kinds`:

```sql
kinds(state, kind) AS (VALUES ('RUN', 'run'), ('FAULT', 'stop'), ('REPAIR', 'stop'), ('WAIT', 'stop'),
                              ('PM', 'stop'), ('OFF', 'stop'), ('STOP', 'stop')),
```

Then classify each piece, continuing from `pieces`. A state's class wins over
its reason's, except that a reason classed planned, idle or external wins
over a repair state (planned work done in it); a state that itself means a
fault of the machine is mapped to `failure`.

```sql
state_classes(state, class) AS (VALUES        -- from the plant: states that say what a stop is
  ('REPAIR', 'repair'), ('PM', 'planned'), ('OFF', 'idle')),
reason_classes(reason, class) AS (VALUES      -- from the plant: which reasons are the machine's own faults
  ('E101', 'failure'), ('E205', 'failure'),
  ('no material', 'external'), ('planned maintenance', 'planned'), ('not scheduled', 'idle')),
classed AS (
  SELECT x.*,
         CASE WHEN x.kind <> 'stop' THEN x.kind                  -- run, unknown
              WHEN sc.class = 'repair' AND rc.class IN ('planned', 'idle', 'external') THEN rc.class
              ELSE coalesce(sc.class, rc.class, 'unclassified') END AS class,
         lead(x.t_start) OVER w AS next_start                    -- later than t_end: a gap follows
  FROM pieces x LEFT JOIN state_classes sc ON sc.state = x.state
                LEFT JOIN reason_classes rc ON rc.reason = x.reason
  WINDOW w AS (PARTITION BY x.machine_id ORDER BY x.t_start)
)
SELECT x.machine_id,
       coalesce(sum(x.s) FILTER (WHERE x.class = 'run'), 0) / 60                     AS run_min,
       coalesce(sum(x.s) FILTER (WHERE x.class IN ('failure', 'repair')), 0) / 60    AS corrective_min,
       coalesce(sum(x.s) FILTER (WHERE x.class = 'planned'), 0) / 60                 AS planned_maintenance_min,
       coalesce(sum(x.s) FILTER (WHERE x.class NOT IN ('run', 'failure', 'repair', 'planned',
                                                       'unclassified', 'unknown')), 0) / 60 AS other_stop_min,
       coalesce(sum(x.s) FILTER (WHERE x.class = 'unclassified'), 0) / 60            AS unclassified_min,
       coalesce(sum(x.s) FILTER (WHERE x.class = 'unknown'), 0) / 60                 AS unknown_state_min,
       (extract(epoch FROM p.t1 - p.t0) - sum(x.s)) / 60                             AS no_data_min,
       coalesce(sum(x.s) FILTER (WHERE x.class = 'planned'), 0)
         / NULLIF(sum(x.s) FILTER (WHERE x.class IN ('failure', 'repair', 'planned')), 0) AS planned_share
FROM (SELECT c.machine_id, c.class,
             extract(epoch FROM least(c.t_end, p.t1) - greatest(c.t_start, p.t0)) AS s
      FROM classed c, params p WHERE c.t_end > p.t0 AND c.t_start < p.t1) x, params p
GROUP BY x.machine_id, p.t0, p.t1;
```

Run this first. Unclassified minutes are stops whose state and reason have no
class: report their share before any figure and ask about them.
`planned_share` is planned maintenance minutes over planned maintenance plus
fault and repair minutes in the range.

## Stops

A stop is a run of stop pieces without a gap, as in `machine-data-sql.md`,
with one difference: fault and repair pieces on both sides of a gap up to
`merge_gap` stay one stop. Continue from `classed`:

```sql
rparams AS (SELECT interval '30 minutes' AS merge_gap),  -- the longest gap inside one failure; 30 min unless the user says
marked AS (
  SELECT c.*,
         CASE WHEN c.kind = 'stop' AND lag(c.kind) OVER w = 'stop'
               AND (lag(c.t_end) OVER w = c.t_start
                    OR (c.class IN ('failure', 'repair') AND lag(c.class) OVER w IN ('failure', 'repair')
                        AND c.t_start - lag(c.t_end) OVER w <= r.merge_gap))
              THEN 0 ELSE 1 END AS new_stop,
         lag(c.class) OVER w IN ('failure', 'repair') AND lag(c.t_end) OVER w < c.t_start AS after_fault_gap
  FROM classed c, rparams r WINDOW w AS (PARTITION BY c.machine_id ORDER BY c.t_start)
),
numbered AS (
  SELECT *, sum(new_stop) OVER (PARTITION BY machine_id ORDER BY t_start) AS stop_no FROM marked
),
framed AS (
  SELECT *, min(t_start) FILTER (WHERE class IN ('failure', 'repair'))
              OVER (PARTITION BY machine_id, stop_no) AS f_start
  FROM numbered WHERE kind = 'stop'
),
stop_list AS (
  SELECT machine_id, stop_no,
         min(t_start) AS started, max(t_end) AS ended, max(next_start) AS next_after,
         sum(t_end - t_start) AS length,                       -- time with data
         bool_or(last_row) AS end_not_seen,
         bool_or(first_row) AS may_have_started_earlier,
         bool_or(class = 'failure') AS has_failure_piece,
         bool_or(class IN ('planned', 'idle')) AS planned_or_idle,
         bool_and(class = 'unclassified') AS unclassified,
         bool_or(new_stop = 1 AND after_fault_gap) AS maybe_same_as_previous,
         min(f_start) AS f_start,
         coalesce(bool_or(class <> 'unclassified') FILTER (WHERE t_start < f_start), false) AS classed_before,
         max(t_end) FILTER (WHERE class IN ('failure', 'repair')) AS f_end,
         max(next_start) FILTER (WHERE class IN ('failure', 'repair')) AS f_next,
         bool_or(last_row) FILTER (WHERE class IN ('failure', 'repair')) AS f_end_not_seen,
         sum(t_end - t_start) FILTER (WHERE class = 'repair') AS active_repair
  FROM framed GROUP BY machine_id, stop_no
)
SELECT s.machine_id, s.started, s.length, s.has_failure_piece, s.planned_or_idle, s.unclassified,
       s.end_not_seen, s.maybe_same_as_previous
FROM stop_list s, params p WHERE s.started >= p.t0 AND s.started < p.t1
ORDER BY s.machine_id, s.started;
```

- A stop counts in the period it began in, as in `machine-data-sql.md`.
- `maybe_same_as_previous`: the stop begins after a gap longer than
  `merge_gap` that followed a fault. It may be the same failure: every
  figure below is then given for both readings. Only sampled data has such
  gaps. Use 30 minutes unless the user gives a limit, and say which.

## Failures from stop reasons or states

A stop with a failure piece is a candidate; continue from `stop_list`:

```sql
fault_stops AS (SELECT s.*, NULL::bigint AS fault_alarms FROM stop_list s WHERE s.has_failure_piece)
SELECT s.machine_id, count(*) FILTER (WHERE s.has_failure_piece) AS fault_stops,
       count(*) FILTER (WHERE s.unclassified) AS unclassified_stops
FROM stop_list s, params p WHERE s.started >= p.t0 AND s.started < p.t1
GROUP BY s.machine_id;
```

## Failures from alarms

When neither states nor reasons name the machine's faults but an alarm table
does, a stop is a candidate when an alarm the plant classes as a fault of the
machine belongs to it. Each alarm belongs to one stop only: the stop it falls
in, otherwise the next stop that begins within the machine's lead and is not
a micro-stop. A fault
alarm during planned maintenance or idle time makes no failure. Use this
block instead of the one above:

```sql
alarm_classes(code, class) AS (VALUES ('A17', 'failure'), ('A22', 'failure'), ('W03', 'operator')),
alarm_leads(machine_id, lead) AS (VALUES ('B', interval '5 minutes')),  -- how early an alarm may precede its stop
attached AS (
  SELECT a.machine_id, a.tsp, a.code, c.class,
         coalesce(
           (SELECT s.stop_no FROM stop_list s
            WHERE s.machine_id = a.machine_id AND a.tsp >= s.started AND a.tsp < s.ended),
           (SELECT s.stop_no FROM stop_list s LEFT JOIN alarm_leads l USING (machine_id)
            WHERE s.machine_id = a.machine_id AND s.started > a.tsp
              AND s.started <= a.tsp + coalesce(l.lead, interval '0')
              AND (s.length >= p.micro_stop OR s.end_not_seen)        -- not a micro-stop
            ORDER BY s.started LIMIT 1)) AS stop_no
  FROM machine_alarms a LEFT JOIN alarm_classes c USING (code), params p
  WHERE a.tsp >= p.t0 - p.lookback AND a.tsp < least(p.t1 + p.lookahead, now())
),
alarmed AS (
  SELECT s.*, x.fault_alarms, x.alarms
  FROM stop_list s CROSS JOIN LATERAL (
    SELECT count(*) FILTER (WHERE a.class = 'failure') AS fault_alarms, count(*) AS alarms
    FROM attached a WHERE a.machine_id = s.machine_id AND a.stop_no = s.stop_no) x
),
fault_stops AS (
  SELECT * FROM alarmed WHERE has_failure_piece OR (fault_alarms > 0 AND NOT planned_or_idle)
)
SELECT a.machine_id,
       count(*) FILTER (WHERE a.fault AND NOT a.micro) AS failures,
       count(*) FILTER (WHERE a.fault AND a.micro) AS short_fault_stops,
       count(*) FILTER (WHERE NOT a.fault AND NOT a.micro AND NOT a.planned_or_idle AND a.alarms = 0) AS stops_without_alarm,
       count(*) FILTER (WHERE NOT a.fault AND NOT a.micro AND NOT a.planned_or_idle AND a.alarms > 0) AS stops_other_alarms,
       count(*) FILTER (WHERE a.fault_alarms > 0 AND a.planned_or_idle) AS planned_with_fault_alarm
FROM (SELECT x.*, x.has_failure_piece OR (x.fault_alarms > 0 AND NOT x.planned_or_idle) AS fault,
             x.length < p.micro_stop AND NOT x.end_not_seen AS micro
      FROM alarmed x, params p WHERE x.started >= p.t0 AND x.started < p.t1) a
GROUP BY a.machine_id;
```

- Two fault alarms in one stop are one failure. Without a fault state, an
  alarm says when the fault was raised, not when it was cleared: the
  restoration time is the whole stop. Check first that alarms and states
  share one clock (`root-cause-checks.md`), and ask for each machine's lead.
- Stops without any alarm are unclassified: report their share first. Fault
  alarms that belong to no stop are no failures; list them apart, and codes
  without a class (`class IS NULL` in `attached`) are asked about:

```sql
SELECT a.machine_id, a.tsp, a.code
FROM attached a, params p
WHERE a.class = 'failure' AND a.stop_no IS NULL AND a.tsp >= p.t0 AND a.tsp < p.t1
ORDER BY a.machine_id, a.tsp;
```

## Failures and their restoration times

Continue from `fault_stops` (either way). A fault stop shorter than the
micro-stop threshold is no failure (unless its end was not seen); count those
apart. Restoration runs from the first fault or repair piece to the last: a
stop that goes on for another reason afterwards (FAULT, then WAIT for
material) ends its restoration where the fault ends, and the rest is a stop
of its own reason (`downtime-losses.md`). When the pieces before the first
fault piece are all unclassified, restoration may have begun at the stop's
start: that is the long end of the range.

```sql
failures AS (
  SELECT f.machine_id, f.stop_no, f.may_have_started_earlier, f.maybe_same_as_previous, f.active_repair,
         f.length AS stop_length,
         coalesce(f.f_start, f.started) AS failed,
         CASE WHEN f.f_start IS NOT NULL AND f.classed_before THEN f.f_start ELSE f.started END AS failed_early,
         coalesce(f.f_end_not_seen, f.end_not_seen) AS end_not_seen,
         coalesce(f.f_end, f.ended) AS restored,
         CASE WHEN f.f_start IS NULL THEN f.next_after ELSE f.f_next END AS restored_by
  FROM fault_stops f, params p
  WHERE f.length >= p.micro_stop OR f.end_not_seen
),
timed AS (
  SELECT f.*,
         (SELECT sum(x.t_end - x.t_start) FROM numbered x          -- time with data: the short end
          WHERE x.machine_id = f.machine_id AND x.stop_no = f.stop_no
            AND x.t_start >= f.failed AND x.t_end <= f.restored) AS restore_low,
         CASE WHEN NOT f.end_not_seen THEN f.restored_by - f.failed_early END AS restore_high
  FROM failures f
)
SELECT t.machine_id, t.failed AT TIME ZONE 'Europe/Berlin' AS failed_local, t.end_not_seen,
       t.end_not_seen AND p.t1 = now() AS ongoing,
       extract(epoch FROM t.restore_low) / 60 AS restore_low_min,
       extract(epoch FROM t.restore_high) / 60 AS restore_high_min,
       extract(epoch FROM (t.restored - t.failed) - t.restore_low) / 60 AS gap_inside_min,
       extract(epoch FROM t.active_repair) / 60 AS active_repair_min, t.maybe_same_as_previous
FROM timed t, params p WHERE t.failed >= p.t0 AND t.failed < p.t1
ORDER BY t.machine_id, t.failed;
```

- `restore_low` and `restore_high` agree unless a gap lies inside or right
  after the failure, or unclassified pieces precede it: then report the range.
- `end_not_seen`: the rows end in the failure. It is `ongoing` only when the
  range ends now; otherwise it lasted at least `restore_low` (read up to t1
  plus the lookahead). Either way it has no restoration time and stays out of
  MTTR.
- `active_repair` is NULL unless the data has a repair state: no repair time,
  not zero. Report for how many failures it was recorded.
- `may_have_started_earlier`: the failure is in the first row read; raise
  the lookback.

## Operating time between failures

Continue from `timed`: the run time from the restoration of the previous
failure to the next failure, and the calendar time beside it.

```sql
gaps AS (SELECT machine_id, t_end AS gap_start FROM classed WHERE next_start > t_end),
spaced AS (
  SELECT t.*, lag(t.restored_by) OVER (PARTITION BY t.machine_id ORDER BY t.failed) AS prev_restored
  FROM timed t
),
tbf AS (
  SELECT s.*,
         (SELECT sum(least(x.t_end, s.failed) - greatest(x.t_start, s.prev_restored))
          FROM pieces x
          WHERE x.machine_id = s.machine_id AND x.kind = 'run' AND x.t_start < s.failed
            AND (s.prev_restored IS NULL OR x.t_end > s.prev_restored)) AS tbf_operating,
         s.failed - s.prev_restored AS tbf_calendar,
         EXISTS (SELECT 1 FROM gaps g
                 WHERE g.machine_id = s.machine_id AND g.gap_start < s.failed
                   AND (s.prev_restored IS NULL OR g.gap_start >= s.prev_restored)) AS tbf_spans_gap
  FROM spaced s
),
counted AS (    -- the failures that began in the range: a failure counts in the period it began in
  SELECT t.*, t.prev_restored IS NOT NULL AND NOT t.tbf_spans_gap
              AND NOT t.maybe_same_as_previous AS tbf_complete
  FROM tbf t, params p WHERE t.failed >= p.t0 AND t.failed < p.t1
)
SELECT machine_id, failed AT TIME ZONE 'Europe/Berlin' AS failed_local, end_not_seen,
       extract(epoch FROM restore_low) / 60 AS restore_low_min,
       extract(epoch FROM restore_high) / 60 AS restore_high_min,
       extract(epoch FROM tbf_operating) / 3600 AS tbf_operating_h,
       extract(epoch FROM tbf_calendar) / 3600 AS tbf_calendar_h, tbf_complete
FROM counted ORDER BY machine_id, failed;
```

- The first failure read has no previous one (`prev_restored` NULL): its
  operating time is "at least", counted from the first row read. A previous
  failure older than the lookback is not seen either.
- A time between failures across a gap (`tbf_spans_gap`), or after a
  failure that may continue the previous one, is incomplete. Only complete
  ones go into a distribution of times between failures.

## Per machine and pooled

Continue from `counted`. Operating time is run time in the range; the
estimate is operating time / failures, which includes the run time after
the last failure, so it differs from the mean of the listed intervals.

```sql
machines AS (   -- machines with data in the range
  SELECT x.machine_id,
         coalesce(sum(least(x.t_end, p.t1) - greatest(x.t_start, p.t0))
                    FILTER (WHERE x.kind = 'run'), interval '0') AS operating
  FROM pieces x, params p WHERE x.t_end > p.t0 AND x.t_start < p.t1
  GROUP BY x.machine_id
),
merged AS (     -- the other reading: a failure after a long gap continues the previous one
  SELECT x.machine_id, bool_or(x.end_not_seen) AS end_not_seen,
         CASE WHEN NOT bool_or(x.end_not_seen) THEN max(x.restored_by) - min(x.failed_early) END AS restore_high
  FROM (SELECT t.*, count(*) FILTER (WHERE NOT t.maybe_same_as_previous)
                      OVER (PARTITION BY t.machine_id ORDER BY t.failed) AS merge_no
        FROM tbf t) x, params p                            -- all failures read, also after t1
  GROUP BY x.machine_id, x.merge_no, p.t0, p.t1
  HAVING min(x.failed) >= p.t0 AND min(x.failed) < p.t1    -- joined failures that began in the range
),
merged_stats AS (   -- restoration at its long end, from the merged reading
  SELECT machine_id, count(*) FILTER (WHERE NOT end_not_seen) AS closed_merged,
         extract(epoch FROM sum(restore_high)) / 60 AS restore_high_min,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM restore_high) / 60)
           FILTER (WHERE NOT end_not_seen) AS median_restore_min,
         percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM restore_high) / 60)
           FILTER (WHERE NOT end_not_seen) AS p90_restore_min,
         extract(epoch FROM max(restore_high)) / 60 AS longest_restore_min
  FROM merged GROUP BY machine_id
),
per_machine AS (
  SELECT m.machine_id,
         extract(epoch FROM m.operating) / 3600 AS operating_h,
         count(c.failed) AS failures,
         count(c.failed) - count(c.failed) FILTER (WHERE c.maybe_same_as_previous) AS failures_low,
         count(c.failed) FILTER (WHERE NOT c.end_not_seen) AS closed,
         count(c.failed) FILTER (WHERE c.end_not_seen) AS end_not_seen,
         (SELECT count(*) FROM fault_stops f, params p
          WHERE f.machine_id = m.machine_id AND f.started >= p.t0 AND f.started < p.t1
            AND f.length < p.micro_stop AND NOT f.end_not_seen) AS short_fault_stops,
         extract(epoch FROM sum(c.restore_low) FILTER (WHERE NOT c.end_not_seen)) / 60 AS restore_low_min,
         count(c.active_repair) AS repair_recorded,
         extract(epoch FROM sum(c.active_repair)) / 60 AS active_repair_min,
         count(*) FILTER (WHERE c.tbf_complete) AS tbf_complete_n,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM c.tbf_operating) / 3600)
           FILTER (WHERE c.tbf_complete) AS tbf_median_h
  FROM machines m LEFT JOIN counted c USING (machine_id)
  GROUP BY m.machine_id, m.operating
),
bounds(n, factor) AS (VALUES    -- 95% lower confidence limit = operating time / factor, steady failure rate
  (0, 2.996), (1, 4.744), (2, 6.296), (3, 7.754), (4, 9.154), (5, 10.513),
  (6, 11.842), (7, 13.148), (8, 14.435), (9, 15.705), (10, 16.962))
SELECT pm.machine_id, pm.operating_h, pm.failures, pm.failures_low, pm.closed, pm.end_not_seen,
       pm.short_fault_stops, ms.median_restore_min,
       CASE WHEN ms.closed_merged >= 10 THEN ms.p90_restore_min END AS p90_restore_min,
       ms.longest_restore_min, pm.repair_recorded, pm.active_repair_min, pm.tbf_complete_n, pm.tbf_median_h,
       pm.operating_h / NULLIF(pm.failures, 0)                    AS mtbf_h,
       pm.operating_h / NULLIF(pm.failures_low, 0)                AS mtbf_high_h,
       pm.failures * 1000 / NULLIF(pm.operating_h, 0)             AS failures_per_1000h,
       pm.failures_low * 1000 / NULLIF(pm.operating_h, 0)         AS failures_low_per_1000h,
       pm.restore_low_min / NULLIF(pm.closed, 0)                  AS mttr_low_min,
       ms.restore_high_min / NULLIF(ms.closed_merged, 0)          AS mttr_high_min,
       pm.operating_h / b.factor                                  AS mtbf_lower_limit_h,
       pm.operating_h / bl.factor                                 AS mtbf_lower_limit_high_h,
       (pm.operating_h / NULLIF(pm.failures, 0))
         / NULLIF(pm.operating_h / NULLIF(pm.failures, 0)
                  + ms.restore_high_min / NULLIF(ms.closed_merged, 0) / 60, 0) AS availability_from_mtbf_mttr
FROM per_machine pm LEFT JOIN merged_stats ms USING (machine_id)
LEFT JOIN bounds b ON b.n = pm.failures LEFT JOIN bounds bl ON bl.n = pm.failures_low
ORDER BY pm.machine_id;
```

Pooled over machines of one type, continue from `per_machine`: sums, then
divide once.

```sql
SELECT count(*) AS machines, sum(pm.operating_h) AS operating_h, sum(pm.failures) AS failures,
       sum(pm.failures_low) AS failures_low, sum(pm.closed) AS closed, sum(pm.end_not_seen) AS end_not_seen,
       sum(pm.operating_h) / NULLIF(sum(pm.failures), 0)                AS mtbf_h,
       sum(pm.operating_h) / NULLIF(sum(pm.failures_low), 0)            AS mtbf_high_h,
       sum(pm.failures) * 1000 / NULLIF(sum(pm.operating_h), 0)         AS failures_per_1000h,
       sum(pm.failures_low) * 1000 / NULLIF(sum(pm.operating_h), 0)     AS failures_low_per_1000h,
       sum(pm.restore_low_min) / NULLIF(sum(pm.closed), 0)              AS mttr_low_min,
       sum(ms.restore_high_min) / NULLIF(sum(ms.closed_merged), 0)      AS mttr_high_min,
       sum(pm.operating_h) / (SELECT factor FROM bounds WHERE n = sum(pm.failures)) AS mtbf_lower_limit_h,
       sum(pm.operating_h) / (SELECT factor FROM bounds WHERE n = sum(pm.failures_low)) AS mtbf_lower_limit_high_h
FROM per_machine pm LEFT JOIN merged_stats ms USING (machine_id);
```

- When a long gap may have split a failure, every figure has two ends:
  `failures_low` to `failures`, `mtbf_h` to `mtbf_high_h`, both failure
  rates and both lower limits. `mttr_low_min` takes each piece's time with
  data as a failure of its own; `mttr_high_min`, the median, the 90th
  percentile (from ten closed failures) and the longest take the long end
  with such failures joined, also across t1. Report both ends. The
  availability then combines the higher count with the long MTTR: it is a
  lower bound, reported as "at least".
- `mtbf_lower_limit_h` is a 95% lower confidence limit, assuming a steady
  failure rate, up to ten failures; with more it is NULL: report the
  estimate with its count.
- A machine with no failure in the range has `mtbf_h` NULL and its lower
  limit: "no failure in 95 operating hours; assuming a steady failure rate,
  MTBF is at least 31.7 h (95% lower confidence limit)". It still adds its
  operating time to a pooled figure.
- A machine with no data in the range is not in `machines`: list it as
  "no data", never as zero failures.
- Never `avg()` an MTBF or MTTR column of several rows: sum the operating
  time, failures and restoration times, then divide.

## Gaps

On samples (`max_gap` set), time without data is neither operating nor
restoring: report it (`no_data_min`). A failure on both sides of a gap up to
`merge_gap` is one failure with a restoration range and its `gap_inside_min`;
the stop list of `machine-data-sql.md` shows it as two stops, so say both
when stops and failures appear in one answer. Across a longer gap the count
is a range. A time between failures across a gap is flagged and left out of
the distribution. On state changes a gap is invisible (`machine-data-sql.md`).

## Keeping it live and boards

A transform keeps one row per machine and month (or week): operating seconds,
failures, `failures_low`, closed failures, the restoration seconds (low and
high), failures whose end was not seen, short fault stops. A second
transform or the board sums them and divides once. On a board, top to
bottom: per machine, failures, MTBF and MTTR with their counts for the
period; the failure rate per month; the longest restorations; failures still
open. A figure that cannot be computed is shown with its reason, never as 0.
