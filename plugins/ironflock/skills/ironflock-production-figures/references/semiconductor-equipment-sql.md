# Equipment state figures of semiconductor tools in SQL

This file shows how the figures of `semiconductor-equipment.md` are computed
from a column that holds a tool's equipment state in the sense of SEMI E10:
hours per state, the availability and utilization variants, failures and the
time or cycles between them, and the efficiencies of SEMI E79. It follows
`machine-data-sql.md` (the same base query, gaps, lookback, duplicates,
counters); read that for everything not said here. Table and column names
are examples (`tool_states` with `tsp, tool_id, state`; `wafer_moves` with
`tsp, tool_id, recipe, wafers, good`, one row per run: a lot on a
single-wafer tool, a batch on a batch tool); use the real ones and state the
fab's time zone (`Europe/Berlin` here). Every pattern was run on test data
whose results were computed by hand first.

## The base query: states mapped to E10

E10 time is calendar time: every hour of the range belongs to one of the six
basic states, so no shift calendar is needed. A value is compared by its key:
letters and digits only, upper case, so `Unscheduled Downtime`,
`unscheduled-downtime` and `UNSCHEDULED_DOWNTIME ` match the same name. A
value whose key is no name is tried by its letters before the first other
character (`UDT-REPAIR`, `SDT_PM`, `PRD2`), the common way of writing a
sub-state; such matches are listed for the user to confirm. `fab_states`
holds the user's answers, compared by the same key; they win, and a label
that is not one of the six codes makes the value `unknown`. Everything else,
NULL included, is `unknown`: never counted in a state, always reported.

```sql
WITH params AS (
  SELECT timestamptz '2026-11-02 00:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-03 00:00 Europe/Berlin') AS t1,
         NULL::interval    AS max_gap,    -- state changes; about twice the interval for samples
         interval '7 days' AS lookback,   -- longer than any state may last
         interval '2 days' AS lookahead   -- how far past t1 a failure's end is read
),
e10_names(name, e10) AS (VALUES
  ('PRODUCTIVE', 'PRD'), ('PRODUCTIVETIME', 'PRD'), ('PRD', 'PRD'), ('PROD', 'PRD'),
  ('STANDBY', 'SBY'), ('STANDBYTIME', 'SBY'), ('SBY', 'SBY'), ('STBY', 'SBY'),
  ('ENGINEERING', 'ENG'), ('ENGINEERINGTIME', 'ENG'), ('ENG', 'ENG'),
  ('SCHEDULEDDOWNTIME', 'SDT'), ('SCHEDULEDDOWN', 'SDT'), ('SDT', 'SDT'),
  ('UNSCHEDULEDDOWNTIME', 'UDT'), ('UNSCHEDULEDDOWN', 'UDT'), ('UDT', 'UDT'),
  ('NONSCHEDULED', 'NST'), ('NONSCHEDULEDTIME', 'NST'), ('NOTSCHEDULED', 'NST'), ('NST', 'NST')),
fab_states(state, e10) AS (VALUES (NULL::text, NULL::text)),  -- the user's answers, e.g. ('ENG-DOWN', 'UDT')
rows_ AS (
  SELECT tool_id, tsp, state FROM tool_states, params p
  WHERE tsp >= p.t0 - p.lookback AND tsp < least(p.t1 + p.lookahead, now())
),
tools AS (      -- an entity table of tools if there is one; else every tool with states or runs
  SELECT tool_id FROM rows_
  UNION SELECT w.tool_id FROM wafer_moves w, params p WHERE w.tsp >= p.t0 AND w.tsp < p.t1  -- no run table: drop
),
fab AS (        -- one answer per key, the label compared without case
  SELECT upper(regexp_replace(state, '[^A-Za-z0-9]', '', 'g')) AS k,
         count(DISTINCT upper(trim(e10))) > 1 AS two_answers,
         CASE WHEN count(DISTINCT upper(trim(e10))) = 1
                   AND min(upper(trim(e10))) IN ('PRD', 'SBY', 'ENG', 'SDT', 'UDT', 'NST')
              THEN min(upper(trim(e10))) ELSE 'unknown' END AS e10
  FROM fab_states WHERE state IS NOT NULL GROUP BY 1
),
mapped AS (     -- each distinct value once: its key, its E10 state and how it was found
  SELECT v.state, v.k, coalesce(f.e10, n.e10, c.e10, 'unknown') AS e10,
         CASE WHEN f.two_answers THEN 'fab list, two answers'
              WHEN f.e10 = 'unknown' THEN 'fab list, not one E10 code'
              WHEN f.e10 IS NOT NULL THEN 'fab list'
              WHEN n.e10 IS NOT NULL THEN 'name'
              WHEN c.e10 IS NOT NULL THEN 'code before a separator' END AS matched_by
  FROM (SELECT DISTINCT state, upper(regexp_replace(state, '[^A-Za-z0-9]', '', 'g')) AS k FROM rows_) v
  LEFT JOIN fab f ON f.k = v.k
  LEFT JOIN e10_names n ON n.name = v.k
  LEFT JOIN e10_names c ON c.name = upper(substring(v.state FROM '^([A-Za-z]+)[^A-Za-z]'))
),
ordered AS (    -- equal time stamps: downtime sorts last and keeps the time
  SELECT r.tool_id, r.tsp, r.state, m.k, m.e10, m.matched_by,
         lead(r.tsp) OVER w AS next_tsp, row_number() OVER w = 1 AS first_row
  FROM rows_ r JOIN mapped m ON m.state IS NOT DISTINCT FROM r.state
  WINDOW w AS (PARTITION BY r.tool_id ORDER BY r.tsp, m.e10 IN ('SDT', 'UDT'), r.state)
),
pieces AS (     -- a row's state until the next row, the end of what was read, or the gap cap
  SELECT * FROM (
    SELECT o.tool_id, o.state, o.k, o.e10, o.matched_by, o.first_row, o.tsp AS t_start,
           least(coalesce(o.next_tsp, now()), p.t1 + p.lookahead,
                 coalesce(o.tsp + p.max_gap, p.t1 + p.lookahead)) AS t_end,
           o.next_tsp IS NULL AS last_row
    FROM ordered o, params p
  ) x WHERE t_end > t_start
),
hours AS (      -- hours per tool and E10 state inside [t0, t1)
  SELECT x.tool_id, x.e10,
         sum(extract(epoch FROM least(x.t_end, p.t1) - greatest(x.t_start, p.t0))) / 3600 AS h
  FROM pieces x, params p WHERE x.t_end > p.t0 AND x.t_start < p.t1
  GROUP BY x.tool_id, x.e10
),
per_tool AS (
  SELECT t.tool_id,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'PRD'), 0) AS prd_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'SBY'), 0) AS sby_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'ENG'), 0) AS eng_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'SDT'), 0) AS sdt_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'UDT'), 0) AS udt_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'NST'), 0) AS nst_h,
         coalesce(sum(h.h) FILTER (WHERE h.e10 = 'unknown'), 0) AS unknown_h,
         extract(epoch FROM p.t1 - p.t0) / 3600 - coalesce(sum(h.h), 0) AS no_data_h
  FROM tools t CROSS JOIN params p LEFT JOIN hours h USING (tool_id)
  GROUP BY t.tool_id, p.t0, p.t1
)
SELECT * FROM per_tool;
```

- The six states plus `unknown_h` plus `no_data_h` add up to the range. A
  tool whose rows begin inside the range (new tool, logger started late) has
  the time before as no data; a tool with runs but no state rows is all no
  data, and its wafers are left out and reported (below). A tool with no row
  since `t0 - lookback` and no run is missing: take the tool list from an
  entity table when there is one. Without a run table, drop the `UNION`
  line of `tools`.
- With state changes a logger outage is invisible: the last state is carried
  through it. With samples, set `max_gap`. Both as in `machine-data-sql.md`.
- A piece across t0 or t1 gives the range only its hours inside it.
- Per day or per shift: split the pieces at the windows with the overlap of
  `machine-data-sql.md` ("Planned production time", `split`, windows of sign
  +1 only); E10 needs no breaks, because every hour has a state.

## Check the mapping first

Before any figure, list every value with its E10 state and how it was found
(continue from `mapped`). Show the list to the user when any value is
`unknown`, from the fab list but rejected (two answers, or not one E10
code), or found by its code before a separator, and ask once.

```sql
SELECT m.state, m.e10, m.matched_by, count(*) AS rows_read, array_agg(DISTINCT r.tool_id) AS tools
FROM rows_ r JOIN mapped m ON m.state IS NOT DISTINCT FROM r.state
GROUP BY m.state, m.e10, m.matched_by
ORDER BY m.e10 = 'unknown' DESC, m.matched_by DESC NULLS FIRST, m.state;
```

- `IDLE`, `RUN`, `DOWN`, `PM`, `BUSY`, `BLOCKED` are not E10 basic states and
  stay `unknown`: IDLE may be standby or non-scheduled, DOWN scheduled or
  unscheduled. The answer goes into `fab_states`, with a code of the six
  (PRD, SBY, ENG, SDT, UDT, NST).
- A code before a separator is often right (`UDT-REPAIR`), but not always:
  `SBY->PRD` and `ENG2PRD` may mean productive, `PRD2` a second chamber,
  and a vendor guide counts engineering on a tool production could not
  have used as downtime (`ENG-DOWN`). Ask; the answer goes into
  `fab_states`. An answer covers every spelling of its key (`eng-down`,
  `ENG_DOWN`), not other words (`Engineering-Down`).

## Availability and utilization

Continue from `per_tool`. Every figure is over time with usable state data:
`total_h` is the sum of the six states, not the length of the range, and the
hours left out are reported beside the figures.

```sql
sums AS (
  SELECT *, prd_h + sby_h + eng_h + sdt_h + udt_h + nst_h AS total_h,   -- total time with state data
            prd_h + sby_h + eng_h + sdt_h + udt_h         AS operations_h,
            prd_h + sby_h + eng_h                         AS uptime_h,
            sdt_h + udt_h                                 AS downtime_h,
            prd_h + sby_h                                 AS manufacturing_h
  FROM per_tool
),
to_core(e10, kind) AS (VALUES   -- the default; change a row where the fab decides otherwise, and say so
  ('PRD', 'run'), ('SBY', 'stop'), ('UDT', 'stop'),
  ('ENG', 'planned stop'), ('SDT', 'planned stop'), ('NST', 'not scheduled')),
core_states(state, kind) AS (VALUES ('SDT-SETUP', 'stop')),  -- the fab's setup sub-states and other exceptions
core_list AS (  -- one kind per key, compared without case; two kinds or another word: rejected (NULL)
  SELECT upper(regexp_replace(state, '[^A-Za-z0-9]', '', 'g')) AS k,
         CASE WHEN count(DISTINCT lower(trim(kind))) = 1
                   AND min(lower(trim(kind))) IN ('run', 'stop', 'planned stop', 'not scheduled')
              THEN min(lower(trim(kind))) END AS kind
  FROM core_states WHERE state IS NOT NULL GROUP BY 1
),
core AS (
  SELECT x.tool_id,
         coalesce(sum(extract(epoch FROM least(x.t_end, p.t1) - greatest(x.t_start, p.t0)))
                  FILTER (WHERE coalesce(s.kind, k.kind) = 'run'), 0) / 3600 AS run_h,
         coalesce(sum(extract(epoch FROM least(x.t_end, p.t1) - greatest(x.t_start, p.t0)))
                  FILTER (WHERE coalesce(s.kind, k.kind) = 'stop'), 0) / 3600 AS stop_h
  FROM pieces x CROSS JOIN params p JOIN to_core k ON k.e10 = x.e10
  LEFT JOIN core_list s ON s.k = x.k
  WHERE x.t_end > p.t0 AND x.t_start < p.t1
  GROUP BY x.tool_id
)
SELECT s.tool_id, s.total_h = 0 AS no_state_data, s.total_h, s.operations_h, s.uptime_h,
       s.unknown_h, s.no_data_h,
       s.uptime_h / NULLIF(s.total_h, 0)        AS total_uptime,
       s.uptime_h / NULLIF(s.operations_h, 0)   AS operational_uptime,
       s.prd_h / NULLIF(s.total_h, 0)           AS total_utilization,
       s.prd_h / NULLIF(s.operations_h, 0)      AS operational_utilization,
       s.prd_h / NULLIF(s.manufacturing_h, 0)   AS productive_share_of_manufacturing,
       c.run_h / NULLIF(c.run_h + c.stop_h, 0)  AS core_availability,
       (SELECT string_agg(DISTINCT cs.state, ', ') FROM core_states cs JOIN core_list l
          ON l.k = upper(regexp_replace(cs.state, '[^A-Za-z0-9]', '', 'g')) WHERE l.kind IS NULL) AS core_states_rejected
FROM sums s LEFT JOIN core c USING (tool_id);
```

- Name each figure with its denominator in the answer: "operational uptime
  72.7% (16 of 22 hours of operations time)". The same tool's day was 58.3%
  total utilization, 63.6% operational utilization, 66.7% total uptime and
  72.7% operational uptime: they differ only by what is divided by what.
- A tool with `no_state_data` is listed as "no data" (or "state values not
  mapped" when its hours are unknown), never as 0%.
- `core_availability` is the availability of `oee.md`: run / (run + stop).
  The default: productive runs; standby and unscheduled downtime are stops;
  engineering and scheduled downtime are planned stops, except setups and
  similar changeovers in scheduled downtime, which are stops as `oee.md`
  says unless the fab counts them as planned; non-scheduled is outside the
  plan. Which sub-states are setups is the fab's answer: put them into
  `core_states` (kinds run, stop, planned stop, not scheduled); rejected
  entries are named in `core_states_rejected` and do not count. Here 14 / 19 = 73.7%; with engineering as a stop,
  14 / 20.
- Planned production time read from the states rests on how the fab books
  non-scheduled time. When idle days without work are booked as
  non-scheduled, it is read from when the tool ran, which `oee.md` forbids:
  ask for the plan and use the calendar of `machine-data-sql.md`.
- Never `avg()` these ratios over tools or days; sum the hours and divide
  again (below).

## Failures, restoring and time off-line

A failure is a run of unscheduled downtime pieces without a gap: `UDT-REPAIR`
followed by `UDT-WAIT-PARTS` is one failure. A downtime event is a run of
scheduled or unscheduled downtime pieces. `repair_states` lists the fab's
repair sub-states. Continue from `per_tool`:

```sql
repair_states(state) AS (VALUES ('UDT-REPAIR')),   -- the fab's repair sub-states, compared by key
marked AS (
  SELECT *,
         CASE WHEN e10 = 'UDT' AND lag(e10) OVER w = 'UDT' AND lag(t_end) OVER w = t_start
              THEN 0 ELSE 1 END AS new_failure,
         CASE WHEN e10 IN ('SDT', 'UDT') AND lag(e10) OVER w IN ('SDT', 'UDT')
                   AND lag(t_end) OVER w = t_start
              THEN 0 ELSE 1 END AS new_down
  FROM pieces WINDOW w AS (PARTITION BY tool_id ORDER BY t_start)
),
numbered AS (  -- a piece is repair, another sub-state, or a bare E10 value (no sub-state)
  SELECT *, sum(new_failure) OVER w AS failure_no, sum(new_down) OVER w AS down_no,
         matched_by <> 'name' AS sub_state,
         k IN (SELECT upper(regexp_replace(state, '[^A-Za-z0-9]', '', 'g')) FROM repair_states) AS repair
  FROM marked WINDOW w AS (PARTITION BY tool_id ORDER BY t_start)
),
events AS (
  SELECT n.tool_id, n.kind, n.no,
         min(n.t_start) AS started, max(n.t_end) AS ended,
         sum(n.t_end - n.t_start) AS length,           -- the whole event, past t1 too
         coalesce(sum(n.t_end - n.t_start) FILTER (WHERE n.repair), interval '0') AS repair,
         bool_and(n.sub_state) AS has_sub_state,     -- every piece has one
         bool_or(n.last_row) AS end_not_seen,
         bool_or(n.first_row) AS may_have_started_earlier
  FROM (SELECT tool_id, t_start, t_end, last_row, first_row, repair, sub_state, 'failure' AS kind, failure_no AS no
        FROM numbered WHERE e10 = 'UDT'
        UNION ALL
        SELECT tool_id, t_start, t_end, last_row, first_row, false, sub_state, 'downtime', down_no
        FROM numbered WHERE e10 IN ('SDT', 'UDT')) n
  GROUP BY n.tool_id, n.kind, n.no
),
reliability AS (   -- an event counts once, in the period it began in
  SELECT t.tool_id, t.prd_h,
         count(e.no) FILTER (WHERE e.kind = 'failure') AS failures,
         count(e.no) FILTER (WHERE e.kind = 'failure' AND e.end_not_seen) AS failures_open,
         extract(epoch FROM avg(e.length) FILTER (WHERE e.kind = 'failure' AND NOT e.end_not_seen)) / 3600
           AS mean_time_to_restore_h,
         extract(epoch FROM avg(e.repair)
                 FILTER (WHERE e.kind = 'failure' AND NOT e.end_not_seen AND e.has_sub_state)) / 3600 AS mean_repair_h,
         count(e.no) FILTER (WHERE e.kind = 'failure' AND NOT e.end_not_seen AND NOT e.has_sub_state)
           AS failures_without_sub_state,
         extract(epoch FROM avg(e.length) FILTER (WHERE e.kind = 'downtime' AND NOT e.end_not_seen)) / 3600
           AS mean_time_offline_h
  FROM per_tool t CROSS JOIN params p
  LEFT JOIN events e ON e.tool_id = t.tool_id AND e.started >= p.t0 AND e.started < p.t1
  GROUP BY t.tool_id, t.prd_h
)
SELECT *, CASE WHEN prd_h > 0 THEN prd_h / NULLIF(failures, 0) END AS mtbf_productive_h
FROM reliability;
```

- Mean productive time between failures = productive hours / failures in the
  range. With no failure it is not a number: "no failure in 16 productive
  hours". With no productive time it is not computable: "no productive
  time", never 0 h. Some fabs divide uptime instead; name it if asked.
- A failure that began before t0 is counted in the period it began in; its
  hours in the range still count as unscheduled downtime. `may_have_started_earlier`
  means its start lies before what was read.
- `mean_time_to_restore_h` is the whole failure, waiting for parts or a
  technician included; `mean_repair_h` only its repair sub-states, averaged
  over the failures whose every piece has a sub-state (a failure that is
  all waiting is 0 h of repair). A failure with a bare `UDT` piece cannot
  be split: it is left out of the repair mean and counted in
  `failures_without_sub_state`;
  name that count beside the mean. A value from the fab list counts as a
  sub-state. Sources and fabs differ on which is "MTTR": ask, and
  name the one shown. Both use failures that began in the range and ended;
  one still open (`failures_open`) is counted as a failure, kept out of the
  means and named ("at least 3 hours so far"). Mean time off-line does the
  same for downtime events.
- Which unscheduled downtime counts as a failure of the tool is the fab's
  decision: waiting for a facility or for out-of-spec material is downtime
  but not the tool's failure. Leave those values out with
  `WHERE e10 = 'UDT' AND state NOT IN (...)` in the failure branch, and say so.

## Cycles, wafers and the E79 efficiencies

Each run takes the state of the piece its finish time falls in. Runs and
wafers in productive time feed E79; runs and wafers in any known state are
cycles for the mean cycles between failures (a batch tool's cycle is a run,
a single-wafer tool's usually a wafer: ask); wafers in unknown state or
without state data are left out and reported. `theory` is the theoretical
production time per wafer, per tool (or tool type) and recipe, from the fab
(example values), never from the data. Continue from `reliability`, with the
CTEs of the availability block before it:

```sql
theory(tool_id, recipe, theoretical_s) AS (VALUES
  ('ETCH-01', 'R1', 240), ('LITHO-03', 'L1', 600), ('CVD-02', 'C1', 300)),
wafers AS (
  SELECT w.tool_id, w.tsp, w.recipe, w.wafers, w.good, x.e10, t.theoretical_s
  FROM wafer_moves w CROSS JOIN params p
  LEFT JOIN pieces x ON x.tool_id = w.tool_id AND w.tsp > x.t_start AND w.tsp <= x.t_end
  LEFT JOIN theory t ON t.tool_id = w.tool_id AND t.recipe = w.recipe
  WHERE w.tsp >= p.t0 AND w.tsp < p.t1
),
wafer_sums AS (
  SELECT tool_id,           -- a run: a distinct finish time and recipe; with a batch or run id, count that
         count(DISTINCT (tsp, recipe)) FILTER (WHERE e10 <> 'unknown') AS runs,
         sum(wafers) FILTER (WHERE e10 <> 'unknown') AS wafer_count,
         count(DISTINCT (tsp, recipe)) FILTER (WHERE e10 NOT IN ('PRD', 'unknown')) AS runs_not_productive,
         bool_and(wafers = 1) AS one_wafer_rows,
         sum(wafers) FILTER (WHERE e10 NOT IN ('PRD', 'unknown')) AS wafers_not_productive,
         sum(wafers) FILTER (WHERE e10 IS NULL OR e10 = 'unknown') AS wafers_left_out,
         array_agg(DISTINCT recipe) FILTER (WHERE e10 = 'PRD' AND theoretical_s IS NULL) AS recipes_without_theory,
         CASE WHEN bool_and(theoretical_s IS NOT NULL) FILTER (WHERE e10 = 'PRD')
              THEN sum(theoretical_s * wafers) FILTER (WHERE e10 = 'PRD') / 3600.0 END AS theo_h,
         CASE WHEN bool_and(theoretical_s IS NOT NULL) FILTER (WHERE e10 = 'PRD')
              THEN sum(theoretical_s * good) FILTER (WHERE e10 = 'PRD') / 3600.0 END AS theo_good_h
  FROM wafers GROUP BY tool_id
),
e79 AS (           -- no run rows: a known zero without productive time, else missing (NULL)
  SELECT s.*, r.failures,
         CASE WHEN w.tool_id IS NOT NULL OR (s.prd_h = 0 AND s.total_h > 0) THEN coalesce(w.runs, 0) END AS runs,
         CASE WHEN w.tool_id IS NOT NULL OR (s.prd_h = 0 AND s.total_h > 0) THEN coalesce(w.wafer_count, 0) END AS wafer_count,
         CASE WHEN w.tool_id IS NOT NULL OR (s.prd_h = 0 AND s.total_h > 0) THEN coalesce(w.runs_not_productive, 0) END
           AS runs_not_productive,
         CASE WHEN w.tool_id IS NOT NULL OR (s.prd_h = 0 AND s.total_h > 0) THEN coalesce(w.wafers_not_productive, 0) END
           AS wafers_not_productive,
         coalesce(w.wafers_left_out, 0) AS wafers_left_out, w.recipes_without_theory, w.one_wafer_rows,
         CASE WHEN s.prd_h = 0 AND s.total_h > 0 THEN coalesce(w.theo_h, 0) ELSE w.theo_h END AS theo_h,
         CASE WHEN s.prd_h = 0 AND s.total_h > 0 THEN coalesce(w.theo_good_h, 0) ELSE w.theo_good_h END AS theo_good_h
  FROM sums s JOIN reliability r USING (tool_id) LEFT JOIN wafer_sums w USING (tool_id)
)
SELECT tool_id, total_h = 0 AS no_state_data, runs, one_wafer_rows, wafer_count, runs_not_productive,
       wafers_not_productive, wafers_left_out, recipes_without_theory,
       runs::numeric / NULLIF(failures, 0)        AS mean_runs_between_failures,
       wafer_count::numeric / NULLIF(failures, 0) AS mean_wafers_between_failures,
       uptime_h / NULLIF(total_h, 0)          AS availability_efficiency,
       uptime_h / NULLIF(operations_h, 0)     AS availability_efficiency_ops,
       prd_h / NULLIF(uptime_h, 0)            AS operational_efficiency,
       theo_h / NULLIF(prd_h, 0)              AS rate_efficiency,
       theo_good_h / NULLIF(theo_h, 0)        AS quality_efficiency,
       theo_good_h / NULLIF(total_h, 0)       AS oee_e79,
       theo_good_h / NULLIF(operations_h, 0)  AS oee_e79_ops
FROM e79;
```

- The four efficiencies multiply to `oee_e79` exactly: theoretical hours for
  the good wafers over total time. `_ops` is the same over operations time;
  name which one is shown (`semiconductor-equipment.md`).
- Cycles count runs in every known state; `runs_not_productive` and
  `wafers_not_productive` say how many came from engineering, standby or
  downtime. Say which states the cycles came from. Look for a batch or run
  id in the run table and ask about it; with one, count distinct ids. Without
  one, a run is a distinct finish time and recipe per tool, so a batch
  logged as several lot rows is one run. On a batch tool whose rows hold one
  wafer each (`one_wafer_rows`) the runs cannot be derived: say so, never
  guess.
- A recipe in `recipes_without_theory` makes rate efficiency, quality
  efficiency and OEE of that tool NULL: "not computable, theoretical time of
  recipe X9 on this tool missing". Runs outside productive time need none.
- Productive time with no run rows: runs, wafers and the cycles between
  failures are missing (NULL), not zero. One cause is
  a run placed at its finish time: a batch that ends after the period
  leaves the period without wafers and puts them into the next one, whose
  rate efficiency can then pass 100%. Check for runs just after t1, prefer
  days over shifts, or, when the data has start and end, share a run's
  theoretical time out by overlap.
- A rate efficiency above 100% is a finding (theoretical time too long, a
  run counted twice, a batch from the period before), never capped.
- Wafers from a counter instead of run rows: the counter steps of
  `machine-data-sql.md` ("Parts from a counter"), placed the same way.

## Several tools or days

Sum the hours, failures and theoretical hours, then divide; one tool without
an input makes the pooled figure NULL. Continue from `e79`:

```sql
SELECT sum(prd_h) / NULLIF(sum(total_h), 0)                AS total_utilization,
       sum(prd_h) / NULLIF(sum(operations_h), 0)           AS operational_utilization,
       sum(uptime_h) / NULLIF(sum(total_h), 0)             AS total_uptime,
       sum(uptime_h) / NULLIF(sum(operations_h), 0)        AS operational_uptime,
       CASE WHEN sum(prd_h) > 0 THEN sum(prd_h) / NULLIF(sum(failures), 0) END AS mtbf_productive_h,
       CASE WHEN bool_and(theo_good_h IS NOT NULL) FILTER (WHERE total_h > 0)
            THEN sum(theo_good_h) / NULLIF(sum(total_h), 0) END AS oee_e79,
       sum(unknown_h) AS unknown_h, sum(no_data_h) AS no_data_h, sum(wafers_left_out) AS wafers_left_out,
       array_agg(tool_id ORDER BY tool_id) FILTER (WHERE total_h = 0) AS tools_without_state_data
FROM e79;
```

Report the hours without data and in unknown state, the wafers left out and
the tools without state data beside the pooled figures.
