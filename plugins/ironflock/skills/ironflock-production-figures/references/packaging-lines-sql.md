# PackML states in SQL

This file turns a PackML state column into the inputs of the core figures:
durations per category, run time and stops in the planned windows split by
where they come from, and starved and blocked time on a line with the
machine each wait points to. The mapping and its reasons are in
`packaging-lines.md`; everything else (parameters, gaps, the lookback, the
calendar, counters, putting OEE together) is in `machine-data-sql.md` and
holds unchanged. Table and column names are examples: `packml_states` with
`tsp, machine_id, state, mode, starved, blocked`, a row at every change.

## The mapping and the pieces

The base query of `machine-data-sql.md` with the PackML mapping in place of
`kinds`. Every later pattern continues from `pieces`, which has the core's
columns plus `category`, `mode` and two flags for unmapped values.

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 06:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-19 14:00 Europe/Berlin') AS t1,
         NULL::interval        AS max_gap,    -- state changes; about twice the interval for samples
         interval '7 days'     AS lookback,   -- longer than any period without production
         interval '1 day'      AS lookahead,
         interval '2 minutes'  AS micro_stop,
         'tr88'                AS numbering   -- 'opc30060' for states numbered 0 to 16
),
packml AS (
  SELECT CASE WHEN p.numbering = 'opc30060' THEN v.n0 ELSE v.n1 END AS code, v.name, v.category
  FROM params p, (VALUES
    (1, 10, 'clearing', 'own_stop'),    (2, 0, 'stopped', 'own_stop'),    (3, 3, 'starting', 'own_stop'),
    (4, 2, 'idle', 'own_stop'),         (5, 12, 'suspended', 'line_stop'), (6, 4, 'execute', 'run'),
    (7, 9, 'stopping', 'own_stop'),     (8, 7, 'aborting', 'own_stop'),   (9, 8, 'aborted', 'own_stop'),
    (10, 14, 'holding', 'own_stop'),    (11, 15, 'held', 'own_stop'),     (12, 16, 'unholding', 'own_stop'),
    (13, 11, 'suspending', 'line_stop'), (14, 13, 'unsuspending', 'line_stop'),
    (15, 1, 'resetting', 'own_stop'),   (16, 5, 'completing', 'own_stop'), (17, 6, 'complete', 'own_stop'),
    (NULL, NULL, 'lack', 'starved'),    (NULL, NULL, 'tailback', 'blocked'),   -- Weihenstephan, by name only
    (NULL, NULL, 'lackbranchline', 'branch_line'), (NULL, NULL, 'tailbackbranchline', 'branch_line'),
    (NULL, NULL, 'equipmentfailure', 'own_stop'),  (NULL, NULL, 'externalfailure', 'own_stop')
  ) v(n1, n0, name, category)
),
modes(code, name, category) AS (VALUES
  (1, 'production', 'production'), (NULL, 'produce', 'production'),
  (2, 'maintenance', 'mode_stop'), (3, 'manual', 'mode_stop')),
rows_ AS (
  SELECT s.machine_id, s.tsp, s.state, s.mode, x.category,
         sm.category IS NULL AS state_unmapped, mm.category IS NULL AS mode_unmapped,
         CASE x.category WHEN 'run' THEN 'run' WHEN 'planned' THEN 'planned'
                         WHEN 'unknown' THEN 'unknown' ELSE 'stop' END AS kind
  FROM (SELECT machine_id, tsp, state::text AS state, mode::text AS mode, starved, blocked,
               btrim(state::text) AS s_trim, btrim(mode::text) AS m_trim,
               lower(regexp_replace(state::text, '[\s_-]', '', 'g')) AS s_name,
               lower(regexp_replace(mode::text, '[\s_-]', '', 'g')) AS m_name
        FROM packml_states, params p
        WHERE tsp >= p.t0 - p.lookback AND tsp < least(p.t1 + p.lookahead, now())) s
  LEFT JOIN packml sm ON sm.name = s.s_name
       OR sm.code = CASE WHEN s.s_trim ~ '^[0-9]+(\.0+)?$' THEN s.s_trim::numeric END
  LEFT JOIN modes mm ON mm.name = s.m_name
       OR mm.code = CASE WHEN s.m_trim ~ '^[0-9]+(\.0+)?$' THEN s.m_trim::numeric END
  CROSS JOIN LATERAL (SELECT CASE
      WHEN mm.category IS NULL THEN 'unknown'               -- mode not mapped, or NULL
      WHEN mm.category <> 'production' THEN mm.category     -- the mode decides, whatever the state
      WHEN sm.category = 'line_stop' AND s.starved AND NOT coalesce(s.blocked, false) THEN 'starved'
      WHEN sm.category = 'line_stop' AND s.blocked AND NOT coalesce(s.starved, false) THEN 'blocked'
      ELSE coalesce(sm.category, 'unknown') END AS category) x
),
ordered AS (    -- equal time stamps: a stop sorts last and keeps the time
  SELECT r.*, lead(r.tsp) OVER w AS next_tsp, row_number() OVER w = 1 AS first_row
  FROM rows_ r
  WINDOW w AS (PARTITION BY r.machine_id ORDER BY r.tsp, r.kind = 'stop', r.state)
),
pieces AS (
  SELECT * FROM (
    SELECT o.machine_id, o.state, o.mode, o.category, o.kind, o.state_unmapped, o.mode_unmapped,
           o.first_row, o.tsp AS t_start,
           least(coalesce(o.next_tsp, now()), p.t1 + p.lookahead,
                 coalesce(o.tsp + p.max_gap, p.t1 + p.lookahead)) AS t_end,
           o.next_tsp IS NULL AS last_row
    FROM ordered o, params p
  ) x WHERE t_end > t_start
)
SELECT machine_id, category, sum(least(t_end, p.t1) - greatest(t_start, p.t0)) AS duration
FROM pieces, params p WHERE t_end > p.t0 AND t_start < p.t1
GROUP BY machine_id, category;
```

- A number is read on the trimmed value (`6`, `' 6 '`, `6.0`, `06`; a sign
  or an exponent is no state); a name in any case, with spaces, underscores
  and hyphens ignored (`EXECUTE`, `Un-Holding`). Weihenstephan states are
  matched by name only. Another spelling is added as a row once the plant
  has confirmed it, never guessed.
- `numbering`: `tr88` for states 1 to 17 (Execute 6), `opc30060` for the
  numbering 0 to 16 of OPC 30060, tobacco machines (Execute 4). Only the
  value most frequent while the counter rises tells them apart (6 or 4); a
  0 or a missing 17 does not. When the data cannot tell, ask.
- `category`: `run`, `own_stop`, `mode_stop` (a non-production mode),
  `starved`, `blocked`, `line_stop` (direction not shown: no tags, or both
  set), `branch_line` (Lack or Tailback of a branch line), `planned` (only
  where the plant maps a mode so) or `unknown`. `kind` is the core's `run`,
  `stop` or `unknown`, plus `planned`.
- The mode decides first: Execute in Maintenance mode is a `mode_stop`,
  never run time. A mode the plant counts as planned gets `'planned'` in
  `modes`; say which and how long. A mode not in `modes` makes the time
  `unknown`. Without a mode column, write `'1' AS mode` and say all time
  counts as Production mode.
- A Weihenstephan program value (`WS_Cur_Prog`) as the mode column takes
  these `modes` rows instead: `(1, 'production', 'production'), (2,
  'startup', 'mode_stop'), (4, 'rundown', 'mode_stop'), (8, 'clean',
  'mode_stop'), (16, 'changeover', 'mode_stop'), (32, 'maintenance',
  'mode_stop'), (64, 'break', 'planned')`. Recognise it by its WS_ name or
  the column description, never by the numbers alone: builders' own PackML
  modes start at 4 too. Break is planned: the plant set it; check it
  against the calendar's breaks. Start Up and Run Down are mode stops, a
  choice to name: they include waiting for product. `WS_Cur_Mode` (off,
  manual, semi-automatic, automatic) is no PackML mode: never map it here.
- `starved` and `blocked` are the tags `EquipmentStarved` and
  `EquipmentBlocked`; write `NULL` for both when they are not logged.
- The range minus the summed durations is time without data, as in the
  core. With samples, set `max_gap`.

State and mode logged as rows of their own: build `packml_states` with one
row at every instant either changes, carrying the other forward. Rows of
one source at the same instant all reach `packml_states`, so the base
query's rule applies (a stop sorts last and keeps the time):

```sql
instants AS (
  SELECT machine_id, tsp FROM state_rows UNION SELECT machine_id, tsp FROM mode_rows
),
packml_states AS (
  SELECT i.machine_id, i.tsp, s.state, m.mode, NULL::boolean AS starved, NULL::boolean AS blocked
  FROM instants i
  LEFT JOIN LATERAL (SELECT r.state::text AS state FROM state_rows r
                     WHERE r.machine_id = i.machine_id
                       AND r.tsp = (SELECT max(q.tsp) FROM state_rows q
                                    WHERE q.machine_id = i.machine_id AND q.tsp <= i.tsp)) s ON true
  LEFT JOIN LATERAL (SELECT r.mode::text AS mode FROM mode_rows r
                     WHERE r.machine_id = i.machine_id
                       AND r.tsp = (SELECT max(q.tsp) FROM mode_rows q
                                    WHERE q.machine_id = i.machine_id AND q.tsp <= i.tsp)) m ON true
),
```

A NULL value is carried as NULL (`unknown`) until the next row of its
source. Read both sources with the same lookback, so that the mode at the
range start is known; before the first mode row the time is `unknown`.
Two rows of one source at one time stamp are a finding, as in the core;
list them (continue from `mode_rows`):

```sql
SELECT 'state' AS source, machine_id, tsp, array_agg(state::text ORDER BY state::text) AS values_
FROM state_rows GROUP BY machine_id, tsp HAVING count(*) > 1
UNION ALL
SELECT 'mode', machine_id, tsp, array_agg(mode::text ORDER BY mode::text)
FROM mode_rows GROUP BY machine_id, tsp HAVING count(*) > 1;
```

## Planned windows: availability and OEE inputs

Continue from `pieces` with `marked` and `numbered` of `machine-data-sql.md`,
then these in place of its `stops` and `classified`: a stop is a micro-stop
only when production follows it directly, so a short hold that turns into a
mode change or a planned mode is never counted as run time.

```sql
stops AS (
  SELECT n.machine_id, n.event_no, sum(n.t_end - n.t_start) AS length,
         bool_or(n.last_row) AS end_not_seen, max(n.t_end) AS ended
  FROM numbered n WHERE n.kind = 'stop'
  GROUP BY n.machine_id, n.event_no
),
classified AS (
  SELECT n.*, coalesce(s.length < p.micro_stop AND NOT s.end_not_seen
                       AND EXISTS (SELECT 1 FROM pieces r WHERE r.machine_id = s.machine_id
                                   AND r.t_start = s.ended AND r.kind = 'run'), false) AS micro
  FROM numbered n LEFT JOIN stops s USING (machine_id, event_no), params p
),
```

Then `calendar` and `planned` of the core, unchanged, and:

```sql
split AS (      -- a micro-stop counts as run time, as in the core
  SELECT c.production_day, c.shift, x.machine_id,
         CASE WHEN x.micro THEN 'run' ELSE x.category END AS category,
         c.sign * extract(epoch FROM least(x.t_end, c.w_end, p.t1) - greatest(x.t_start, c.w_start)) AS s
  FROM classified x JOIN calendar c ON x.t_start < c.w_end AND x.t_end > c.w_start, params p
  WHERE least(x.t_end, c.w_end, p.t1) > greatest(x.t_start, c.w_start)
),
per_window AS (
  SELECT p.production_day, p.shift, m.machine_id, p.planned_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'run'), 0)         AS run_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'own_stop'), 0)    AS own_stop_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'mode_stop'), 0)   AS mode_stop_s,
         coalesce(sum(s.s) FILTER (WHERE s.category IN ('starved', 'blocked', 'line_stop', 'branch_line')), 0)
                                                                         AS line_stop_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'starved'), 0)     AS starved_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'blocked'), 0)     AS blocked_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'planned'), 0)     AS mode_planned_s,
         coalesce(sum(s.s) FILTER (WHERE s.category = 'unknown'), 0)     AS unknown_s,
         p.planned_s - coalesce(sum(s.s), 0)                             AS no_data_s
  FROM planned p CROSS JOIN (SELECT DISTINCT machine_id FROM pieces) m
  LEFT JOIN split s ON s.production_day = p.production_day AND s.shift = p.shift
                   AND s.machine_id = m.machine_id
  GROUP BY p.production_day, p.shift, m.machine_id, p.planned_s
)
SELECT production_day, shift, machine_id, planned_s, mode_planned_s, run_s,
       own_stop_s + mode_stop_s + line_stop_s AS stop_s,
       own_stop_s, mode_stop_s, line_stop_s, starved_s, blocked_s, unknown_s, no_data_s,
       run_s::numeric / NULLIF(run_s + own_stop_s + mode_stop_s + line_stop_s, 0) AS availability
FROM per_window;
```

- Run + stops + mode-planned + unknown + no data = the calendar's planned
  time. `line_stop_s` holds starved, blocked, direction unknown and branch
  line; availability counts every stop alike.
- Time in a mode mapped `planned` leaves the planned production time, as a
  break does. Feed the core's "Putting OEE together" with this row
  (continue from `per_window`; `counts` holds total, good, `ideal_s` and
  `ideal_good_s` per machine and window from the counter patterns):

```sql
per_shift AS (
  SELECT w.machine_id, w.production_day, w.shift,
         w.planned_s - w.mode_planned_s AS planned_s, w.mode_planned_s, w.run_s,
         w.own_stop_s + w.mode_stop_s + w.line_stop_s AS stop_s,
         c.total, c.good, c.ideal_s, c.ideal_good_s
  FROM per_window w
  LEFT JOIN counts c USING (machine_id, production_day, shift)
),
```

- Counts: run the counter pattern on the `AccCount` of `ProdProcessedCount`
  and of `ProdDefectiveCount`. Total = processed; good ranges from
  processed `parts_low` minus defective `parts_high` to processed
  `parts_high` minus defective `parts_low`; report one figure only when
  both ends agree. Place the steps with this instead of the core's
  `placed` (continue from its `judged` and from `classified` above): parts
  made in a mode stop or a planned mode are no output and are reported
  apart, as are parts in an unknown state or without data.

```sql
placed AS (
  SELECT c.production_day, c.shift, c.sign, j.*, coalesce(x.category, 'no_data') AS at_category
  FROM judged j JOIN calendar c ON j.tsp > c.w_start AND j.tsp <= c.w_end
  LEFT JOIN classified x ON x.machine_id = j.machine_id AND j.tsp > x.t_start AND j.tsp <= x.t_end
)
SELECT production_day, shift, machine_id,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev
                               WHEN 'rollover' THEN counter + 65536 - prev ELSE 0 END)
         FILTER (WHERE as_output) AS parts_low,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev
                               WHEN 'rollover' THEN counter + 65536 - prev
                               WHEN 'implausible' THEN counter - prev
                               WHEN 'jitter' THEN 0 ELSE counter END)
         FILTER (WHERE as_output) AS parts_high,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev ELSE 0 END)
         FILTER (WHERE at_category IN ('mode_stop', 'planned')) AS parts_in_mode,
       sum(sign * CASE verdict WHEN 'count' THEN counter - prev ELSE 0 END)
         FILTER (WHERE at_category IN ('unknown', 'no_data')) AS parts_left_out
FROM (SELECT *, at_category NOT IN ('mode_stop', 'planned', 'unknown', 'no_data') AS as_output FROM placed) q
GROUP BY production_day, shift, machine_id;
```

## Values the mapping does not know

Continue from `pieces`; list these before any figure and ask about each. A
state the mapping does not know is listed even where a mode decided the
time:

```sql
SELECT machine_id, state, mode, state_unmapped, mode_unmapped, count(*) AS pieces_,
       sum(least(t_end, p.t1) - greatest(t_start, p.t0)) AS duration
FROM pieces, params p
WHERE (state_unmapped OR mode_unmapped) AND t_end > p.t0 AND t_start < p.t1
GROUP BY machine_id, state, mode, state_unmapped, mode_unmapped;
```

## Starved and blocked on a line

`line` gives each machine's place, upstream to downstream (from the plant);
`counters` the part counter readings (`AccCount`) of its machines (`SELECT
NULL::text, NULL::timestamptz, NULL::numeric WHERE false` where there are
none). Pieces of one wait (the same line stop category, back
to back) form one wait. Each wait is cut into slices at every change on the
line; in each slice the search walks from the waiting machine in its
direction (upstream when starved, downstream when blocked, both when
unknown). It passes machines that wait the same way or in an unknown
direction, and machines that run without output (the last readings at or
before the slice's start and end are equal). A machine that runs and produces ends the
search without a cause (a buffer between feeds it), as does a blocked
machine upstream or a starved one downstream. A running machine without
counter readings is passed, and the cause found beyond it is flagged
`through_running`. The first other machine is the cause (an own stop, a
mode, an unknown state, no data, its branch line). Continue from `pieces`:

```sql
line(machine_id, position) AS (VALUES ('R1', 1), ('F1', 2), ('L1', 3)),
counters(machine_id, tsp, counter) AS (
  SELECT machine_id, tsp, counter FROM part_counter, params p
  WHERE tsp >= p.t0 - p.lookback AND tsp < p.t1 + p.lookahead
),
wait_marked AS (
  SELECT x.*, l.position,
         CASE WHEN lag(x.category) OVER w = x.category AND lag(x.t_end) OVER w = x.t_start
              THEN 0 ELSE 1 END AS new_wait
  FROM pieces x JOIN line l USING (machine_id)
  WINDOW w AS (PARTITION BY x.machine_id ORDER BY x.t_start)
),
waits AS (
  SELECT g.machine_id, g.position, g.category, g.wait_no,
         greatest(min(g.t_start), p.t0) AS w0, least(max(g.t_end), p.t1) AS w1,
         max(g.t_end) - min(g.t_start) < p.micro_stop AND NOT bool_or(g.last_row) AS short
  FROM (SELECT *, sum(new_wait) OVER (PARTITION BY machine_id ORDER BY t_start) AS wait_no
        FROM wait_marked) g, params p
  WHERE g.category IN ('starved', 'blocked', 'line_stop', 'branch_line')
  GROUP BY g.machine_id, g.position, g.category, g.wait_no, p.t0, p.t1, p.micro_stop
  HAVING max(g.t_end) > p.t0 AND min(g.t_start) < p.t1
),
cuts AS (
  SELECT machine_id, wait_no, w0 AS t FROM waits
  UNION
  SELECT w.machine_id, w.wait_no, b.t
  FROM waits w JOIN (SELECT t_start AS t FROM wait_marked UNION SELECT t_end FROM wait_marked) b
    ON b.t > w.w0 AND b.t < w.w1
),
slices AS (
  SELECT w.machine_id, w.wait_no, w.position, w.category, c.t AS s0,
         coalesce(lead(c.t) OVER (PARTITION BY c.machine_id, c.wait_no ORDER BY c.t), w.w1) AS s1
  FROM cuts c JOIN waits w USING (machine_id, wait_no)
  WHERE NOT w.short AND w.category <> 'branch_line'
),
seen AS (       -- what each machine in the search direction did in the slice
  SELECT s.machine_id, s.wait_no, s.s0, d.dir, o.machine_id AS other,
         abs(o.position - s.position) AS distance,
         CASE WHEN x.category <> 'run' THEN x.category
              WHEN x.category IS NULL THEN 'no_data'
              WHEN lo.counter IS NULL OR hi.counter IS NULL THEN 'run_unmetered'
              WHEN lo.counter <> hi.counter THEN 'producing'
              ELSE 'running_empty' END AS other_category
  FROM slices s
  CROSS JOIN (VALUES ('up'), ('down')) d(dir)
  JOIN line o ON (d.dir = 'up' AND o.position < s.position AND s.category IN ('starved', 'line_stop'))
              OR (d.dir = 'down' AND o.position > s.position AND s.category IN ('blocked', 'line_stop'))
  LEFT JOIN wait_marked x ON x.machine_id = o.machine_id AND x.t_start <= s.s0 AND x.t_end > s.s0
  LEFT JOIN LATERAL (SELECT k.counter FROM counters k WHERE k.machine_id = o.machine_id
                     AND k.tsp <= s.s0 ORDER BY k.tsp DESC LIMIT 1) lo ON x.category = 'run'
  LEFT JOIN LATERAL (SELECT k.counter FROM counters k WHERE k.machine_id = o.machine_id
                     AND k.tsp <= s.s1 ORDER BY k.tsp DESC LIMIT 1) hi ON x.category = 'run'
),
walked AS (
  SELECT *, coalesce(bool_or(other_category = 'run_unmetered') OVER (
              PARTITION BY machine_id, wait_no, s0, dir ORDER BY distance
              ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), false) AS through_running
  FROM seen
),
first_other AS (
  SELECT DISTINCT ON (machine_id, wait_no, s0, dir) *
  FROM walked
  WHERE other_category NOT IN ('running_empty', 'run_unmetered', 'line_stop')
    AND NOT (dir = 'up' AND other_category = 'starved')
    AND NOT (dir = 'down' AND other_category = 'blocked')
  ORDER BY machine_id, wait_no, s0, dir, distance
),
chosen AS (     -- the nearer side; two at the same distance share the slice
  SELECT *, count(*) OVER (PARTITION BY machine_id, wait_no, s0) AS sharing
  FROM (SELECT *, rank() OVER (PARTITION BY machine_id, wait_no, s0 ORDER BY distance) AS nearness
        FROM first_other
        WHERE other_category <> 'producing'
          AND NOT (dir = 'up' AND other_category = 'blocked')
          AND NOT (dir = 'down' AND other_category = 'starved')) f
  WHERE nearness = 1
),
attributed AS (
  SELECT s.machine_id, s.wait_no, s.category, s.s0, s.s1, c.other AS cause,
         c.other_category AS cause_category, coalesce(c.through_running, false) AS through_running,
         (s.s1 - s.s0) / coalesce(c.sharing, 1) AS duration
  FROM slices s LEFT JOIN chosen c USING (machine_id, wait_no, s0)
  UNION ALL     -- not searched: short waits and waits for a branch line
  SELECT machine_id, wait_no, category, w0, w1, NULL,
         CASE WHEN category = 'branch_line' THEN 'branch_line' ELSE 'short' END, false, w1 - w0
  FROM waits WHERE short OR category = 'branch_line'
)
SELECT cause, cause_category, through_running, sum(duration) AS line_stop_time,
       count(DISTINCT (machine_id, wait_no)) AS waits,
       array_agg(DISTINCT machine_id) AS machines_waiting
FROM attributed GROUP BY cause, cause_category, through_running;
```

- Cause plus no cause (`cause` NULL: a producing machine, a blocked
  machine upstream, a starved one downstream, the line's end), short and
  branch line add up to the waited time. Rank causes by minutes and by
  waits, as `downtime-losses.md` says; a wait with several causes counts
  for each. Starved and blocked time per machine is `waits` summed by
  machine and category.
- The slices assume the machines' clocks agree to within seconds. A wait
  shorter than `micro_stop` is not searched (`short`): clock skew and the
  buffer between machines make its cause uncertain. The buffer also delays
  every effect, so the minutes just after a cause has ended may show no
  cause. The counter may be sampled at a fixed interval or written on
  change: no reading inside the slice means no output. A logger outage
  therefore looks like running empty, and a counter reset in the slice
  counts as output, so the search ends there without a cause.
- A cause is a candidate, not proof. Say when it was found
  `through_running`: a running machine without a counter may have been
  slow, and then a stopped machine further on is blamed.
