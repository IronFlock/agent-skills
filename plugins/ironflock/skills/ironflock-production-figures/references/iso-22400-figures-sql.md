# Further ISO 22400 figures from machine data in SQL

This file computes the figures of `iso-22400-figures.md` (setup ratio,
technical efficiency, allocation and utilisation efficiency, failure and
repair times, first pass yield, scrap and rework) in PostgreSQL with
TimescaleDB. It continues the queries of `machine-data-sql.md` and uses its
conventions: example names (`machine_states`, `part_counter`, time column
`tsp`), the real ones used instead, the plant's time zone (`Europe/Berlin`
here) stated in every result, `numeric` before dividing, every ratio guarded
with `NULLIF(..., 0)`, never `avg()` of a ratio column. Run the mapping
checks at the end of this file first.

## Setup, faults and orders over the planned windows

Continue the query of "Planned production time" in `machine-data-sql.md`:
its base query with the setup state as a stop in `kinds` (for example
`('SETUP', 'stop')`), then `marked` to `split`. Every stop state is also
given a class here: `setup`, `fault` (a fault of the machine itself) or
`other` (waiting, no material, no operator). Orders come from a table of
order intervals per machine (`production_orders` here), an order still on
the machine with `o_end` NULL (it counts until t1); with an order or batch
column in the state rows, build the same intervals from it. Without any
order data, leave out `in_orders` and `busy`: the order figures are not
computable.

```sql
stop_classes(state, cls) AS (VALUES ('SETUP', 'setup'), ('FAULT', 'fault'), ('WAIT', 'other'), ('STOP', 'other')),
split_cls AS (  -- as split, with the class of each stop piece
  SELECT c.production_day, c.shift, c.sign, c.w_start, c.w_end, x.machine_id, x.t_start, x.t_end,
         CASE WHEN x.kind = 'run' OR x.micro THEN 'run'
              WHEN x.kind = 'stop' THEN coalesce(sc.cls, 'unclassified')
              WHEN sc.cls IS NOT NULL THEN 'unclassified'   -- classed, but not a stop in kinds
              ELSE 'unknown' END AS cls,
         c.sign * extract(epoch FROM least(x.t_end, c.w_end, p.t1) - greatest(x.t_start, c.w_start)) AS s
  FROM classified x JOIN calendar c ON x.t_start < c.w_end AND x.t_end > c.w_start
  LEFT JOIN stop_classes sc ON sc.state = x.state, params p
  WHERE least(x.t_end, c.w_end, p.t1) > greatest(x.t_start, c.w_start)
),
in_orders AS (  -- the same pieces, clipped to the orders as well
  SELECT x.production_day, x.shift, x.machine_id, x.cls,
         x.sign * extract(epoch FROM least(x.t_end, x.w_end, p.t1, o.o_end)
                                   - greatest(x.t_start, x.w_start, o.o_start)) AS s
  FROM split_cls x JOIN production_orders o ON o.machine_id = x.machine_id, params p
  WHERE least(x.t_end, x.w_end, p.t1, o.o_end) > greatest(x.t_start, x.w_start, o.o_start)
),
busy AS (
  SELECT production_day, shift, machine_id,
         sum(s) FILTER (WHERE cls <> 'unknown') AS busy_s,
         sum(s) FILTER (WHERE cls = 'run')      AS run_in_orders_s
  FROM in_orders GROUP BY production_day, shift, machine_id
),
per_shift AS (
  SELECT x.production_day, x.shift, x.machine_id, pl.planned_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'run'), 0)          AS run_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'setup'), 0)        AS setup_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'fault'), 0)        AS fault_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'other'), 0)        AS other_stop_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'unclassified'), 0) AS unclassified_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls = 'unknown'), 0)      AS unknown_s,
         coalesce(sum(x.s) FILTER (WHERE x.cls <> 'unknown'), 0)     AS known_s,
         pl.planned_s - coalesce(sum(x.s) FILTER (WHERE x.cls <> 'unknown'), 0) AS left_out_s,
         coalesce(max(b.busy_s), 0)                                  AS busy_s,
         coalesce(max(b.run_in_orders_s), 0)                         AS run_in_orders_s,
         EXISTS (SELECT 1 FROM production_orders o            -- order data for this machine at all
                 WHERE o.machine_id = x.machine_id) AS has_orders,
         (SELECT CASE WHEN bool_or(o.o_end IS NULL) THEN 'infinity'::timestamptz ELSE max(o.o_end) END
          FROM production_orders o WHERE o.machine_id = x.machine_id) AS last_order_end
  FROM split_cls x JOIN planned pl USING (production_day, shift)
  LEFT JOIN busy b USING (production_day, shift, machine_id)
  GROUP BY x.production_day, x.shift, x.machine_id, pl.planned_s
),
figures AS (    -- no usable state data: left out, listed as the core query lists it
  SELECT *,
         CASE WHEN unclassified_s = 0 THEN setup_s::numeric / NULLIF(run_s + setup_s, 0) END AS setup_ratio,
         CASE WHEN unclassified_s = 0 THEN run_s::numeric / NULLIF(run_s + fault_s, 0) END   AS technical_efficiency,
         CASE WHEN has_orders THEN busy_s::numeric / NULLIF(known_s, 0) END                   AS allocation_efficiency,
         CASE WHEN has_orders THEN run_in_orders_s::numeric / NULLIF(busy_s, 0) END           AS utilisation_efficiency,
         CASE WHEN has_orders THEN run_s - run_in_orders_s END                                AS run_outside_orders_s
  FROM per_shift WHERE known_s > 0
)
SELECT * FROM figures;
```

- Setup, fault and run time are clipped to the planned windows like run
  and stop time in the core; micro-stops are run time, so a one-minute
  setup is too. A stop state without a class, or a classed state that
  `kinds` does not map as a stop, makes setup ratio, technical efficiency
  and failures NULL: list it (the checks at the end) and ask.
- Report `left_out_s` (unknown state and no data; `unknown_s` is the
  unknown part) beside every figure: the figures are over known time only.
- Allocation x utilisation efficiency = availability - run outside orders /
  known time. A machine without any order rows has no order figures
  (NULL); one with order rows but none in the shift has allocation 0%, a
  known zero only while its order data is current: when `last_order_end`
  (infinity for an open order) lies before the period, report "no current
  order data" instead of 0%. With an index on the order table's machine column the test
  for order rows is cheap.
- A setup ratio with no run and no setup is NULL, never 0%; a machine that
  stood still in a fault all shift has technical efficiency 0%.

Pooled over machines or shifts, continue from `figures`:

```sql
SELECT CASE WHEN bool_and(unclassified_s = 0)
            THEN sum(setup_s)::numeric / NULLIF(sum(run_s + setup_s), 0) END AS setup_ratio,
       CASE WHEN bool_and(unclassified_s = 0)
            THEN sum(run_s)::numeric / NULLIF(sum(run_s + fault_s), 0) END   AS technical_efficiency,
       CASE WHEN bool_and(has_orders)
            THEN sum(busy_s)::numeric / NULLIF(sum(known_s), 0) END          AS allocation_efficiency,
       CASE WHEN bool_and(has_orders)
            THEN sum(run_in_orders_s)::numeric / NULLIF(sum(busy_s), 0) END  AS utilisation_efficiency,
       sum(run_outside_orders_s)                                             AS run_outside_orders_s,
       sum(left_out_s)                                                       AS left_out_s
FROM figures;
```

Checked on an early shift (06:00 to 14:00, break 10:00 to 10:30, planned
450 minutes, state changes, micro-stop threshold 2 minutes): M1 with a
setup from 05:50 to 06:20, two faults of 30 and 20 minutes, a one-minute
wait, a 40-minute setup, orders until 13:30; M2 without data before 10:30
(240 minutes left out), one 30-minute setup; M3 in a fault from 07:00; M4
in a fault since the day before; M3 and M4 without orders. Setup ratio M1
60/400 = 15.0%, M2 30/210 = 14.3%, M3 0%, M4 not computable, pooled 90/670
= 13.4% (the mean of the three ratios: 9.8%; setup over planned time of all
four: 5.0%). Technical efficiency M1 340/390 = 87.2%, pooled 580/1470 =
39.5% (mean of ratios 50.1%). M1: allocation 420/450 = 93.3%, utilisation
310/420 = 73.8%, availability 75.6% with 30 minutes run outside orders; M3
and M4: no order figures, so none pooled.

Orders of one machine must not overlap, or their time counts twice; any row
is a finding:

```sql
SELECT a.machine_id, a.order_no, b.order_no AS overlaps_with
FROM production_orders a JOIN production_orders b
  ON a.machine_id = b.machine_id AND a.order_no < b.order_no
 AND a.o_start < b.o_end AND b.o_start < a.o_end;
```

## Failures: MTTR and MOTBF

A failure is a stop whose first state has the class `fault`, not a
micro-stop, that began in the period and whose fault lies at least partly
inside a planned window, so that failures and fault time agree; one that
lies wholly in a break or outside the shifts is listed apart
(`outside_plan`).
Its repair time is the length of its fault pieces, whole (breaks included,
read past t1); waiting after the fault is not repair. Continue from
`figures` above, with `numbered`, `stops` and `calendar` of the core:

```sql
fault_pieces AS (
  SELECT n.machine_id, n.event_no, sum(n.t_end - n.t_start) AS fault_length,
         bool_or(n.last_row) AS fault_end_not_seen
  FROM numbered n JOIN stop_classes c ON c.state = n.state AND c.cls = 'fault'
  GROUP BY n.machine_id, n.event_no
),
fault_in_plan AS (  -- seconds of each stop's fault pieces inside the planned windows
  SELECT n.machine_id, n.event_no,
         sum(c.sign * extract(epoch FROM least(n.t_end, c.w_end) - greatest(n.t_start, c.w_start))) AS s
  FROM numbered n JOIN stop_classes sc ON sc.state = n.state AND sc.cls = 'fault'
  JOIN calendar c ON n.t_start < c.w_end AND n.t_end > c.w_start
  GROUP BY n.machine_id, n.event_no
),
failures AS (
  SELECT s.machine_id, f.fault_length, f.fault_end_not_seen,
         s.started >= p.t0 AND s.started < p.t1 AS counted_in_range,   -- counted in the period it began
         coalesce(fp.s, 0) > 0 AS in_plan
  FROM stops s JOIN stop_classes c ON c.state = s.first_state AND c.cls = 'fault'
  JOIN fault_pieces f USING (machine_id, event_no)
  LEFT JOIN fault_in_plan fp USING (machine_id, event_no), params p
  WHERE s.ended > p.t0 AND s.started < p.t1
    AND NOT (s.length < p.micro_stop AND NOT s.end_not_seen)
),
per_machine AS (    -- every machine with state data, also those without a failure
  SELECT r.machine_id, r.run_s, r.classified,
         count(f.machine_id) FILTER (WHERE f.counted_in_range AND f.in_plan)              AS failures,
         count(f.machine_id) FILTER (WHERE f.counted_in_range AND f.in_plan
                                       AND NOT f.fault_end_not_seen)                      AS ended,
         extract(epoch FROM sum(f.fault_length) FILTER (WHERE f.counted_in_range AND f.in_plan
                                                          AND NOT f.fault_end_not_seen))  AS repair_s,
         count(f.machine_id) FILTER (WHERE f.counted_in_range AND NOT f.in_plan)          AS outside_plan,
         count(f.machine_id) FILTER (WHERE f.fault_end_not_seen)                          AS not_ended
  FROM (SELECT machine_id, sum(run_s) AS run_s, bool_and(unclassified_s = 0) AS classified
        FROM figures GROUP BY machine_id) r
  LEFT JOIN failures f USING (machine_id)
  GROUP BY r.machine_id, r.run_s, r.classified
)
SELECT machine_id, run_s, classified, outside_plan, not_ended,
       CASE WHEN classified THEN failures END                             AS failures,
       CASE WHEN classified THEN repair_s::numeric / NULLIF(ended, 0) END AS mttr_s,
       CASE WHEN classified THEN run_s::numeric / NULLIF(failures, 0) END AS motbf_s
FROM per_machine
UNION ALL
SELECT 'all machines', sum(run_s), bool_and(classified), sum(outside_plan), sum(not_ended),
       CASE WHEN bool_and(classified) THEN sum(failures) END,
       CASE WHEN bool_and(classified) THEN sum(repair_s)::numeric / NULLIF(sum(ended), 0) END,
       CASE WHEN bool_and(classified) THEN sum(run_s)::numeric / NULLIF(sum(failures), 0) END
FROM per_machine;
```

- A failure whose fault has not ended is left out of MTTR and listed
  (`not_ended`) with its minutes so far, also when it began earlier.
- A machine without a failure has `motbf_s` NULL: report "no failure in
  `run_s` of run time"; its run time stays in the pooled sum. With a stop
  state without a class, failures, MTTR and MOTBF are NULL.
- This MTTR differs from the rough one of `downtime-losses.md`, which takes
  each stop's minutes inside the period, waiting included: a fault from
  21:30 to 22:20 with the period ending at 22:00 is 30 minutes there and 50
  here. Name which one is reported.
- Checked on the shift above: M1 MTTR 25 min, MOTBF 340/2 = 170 min; M2
  no failure in 180 min; M3 one failure of 480 min (07:00 to 15:00, read
  past t1), MOTBF 60 min; M4 not ended, listed. Pooled MTTR 530/3 = 176.7
  min, MOTBF 580/3 = 193.3 min (the mean of the machines' MOTBF: 115 min).
  And on a day of two shifts: a fault from 08:00 followed by 20 minutes of
  waiting counts 30 minutes, a fault wholly in a break is listed apart
  (MOTBF 640 minutes, not 320), one from 10:25 to 10:40 with the break
  ending 10:30 counts, a 30-minute stop without a class gives no figure
  instead of "no failure".

## First pass yield, scrap and rework from part results

One row per pass of a part (`part_results`: `tsp, machine_id, part_id,
result`). Map the result values like `kinds`; an empty or unmapped one is
`unknown`, left out and counted apart, as are rows without a part id.
Identical rows count once; two different results at one time are a finding
(the checks at the end). The first pass of a part is looked for over a
lookback, so that a pass after rework is never taken for a first one; the
final outcome is the part's latest pass up to now. The produced quantity is
first passes and passes after rework; a part tested again after a good or
scrap result is a repeat pass, left out and counted apart. Counted over the period: join the passes to
`calendar` as the core joins counter steps to clip them to planned windows.

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 06:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-19 14:00 Europe/Berlin') AS t1,
         interval '7 days' AS lookback               -- longer than a part stays in rework
),
machines(machine_id) AS (VALUES ('M1'), ('M2'), ('M3')),   -- the machines asked about
outcomes(result, outcome) AS (VALUES ('OK', 'good'), ('SCRAP', 'scrap'), ('REWORK', 'rework')),
rows_ AS (
  SELECT DISTINCT r.machine_id, r.part_id, r.tsp, coalesce(o.outcome, 'unknown') AS outcome
  FROM part_results r LEFT JOIN outcomes o USING (result), params p
  WHERE r.tsp >= p.t0 - p.lookback
),
passes AS (
  SELECT x.*, row_number() OVER w = 1 AS first_pass, lag(x.outcome) OVER w AS prev_outcome,
         first_value(x.outcome) OVER (PARTITION BY x.machine_id, x.part_id ORDER BY x.tsp DESC) AS final_outcome
  FROM rows_ x WHERE x.part_id IS NOT NULL
  WINDOW w AS (PARTITION BY x.machine_id, x.part_id ORDER BY x.tsp)
),
in_range AS (  -- produced: first passes and passes after rework
  SELECT ps.*, ps.first_pass OR ps.prev_outcome = 'rework' AS produced
  FROM passes ps, params p WHERE ps.tsp >= p.t0 AND ps.tsp < p.t1
),
per_machine AS (
  SELECT m.machine_id,
         count(x.part_id) FILTER (WHERE x.first_pass AND x.outcome <> 'unknown') AS first_passes,
         count(x.part_id) FILTER (WHERE x.first_pass AND x.outcome = 'good')     AS good_first,
         count(x.part_id) FILTER (WHERE x.first_pass AND x.outcome = 'scrap')    AS scrap_first,
         count(x.part_id) FILTER (WHERE x.first_pass AND x.outcome = 'rework')   AS rework_first,
         count(x.part_id) FILTER (WHERE x.first_pass AND x.outcome <> 'unknown'
                                    AND x.final_outcome = 'good')               AS finally_good,
         count(x.part_id) FILTER (WHERE x.produced AND x.outcome <> 'unknown')   AS passes,
         count(x.part_id) FILTER (WHERE x.produced AND NOT x.first_pass
                                    AND x.outcome <> 'unknown')                 AS later_passes,
         count(x.part_id) FILTER (WHERE NOT x.produced)                          AS repeat_passes,
         count(x.part_id) FILTER (WHERE x.produced AND x.outcome = 'scrap')      AS scrap_passes,
         count(x.part_id) FILTER (WHERE x.produced AND x.outcome = 'rework')     AS rework_passes,
         count(x.part_id) FILTER (WHERE x.outcome = 'unknown')                   AS unknown_results,
         (SELECT count(*) FROM rows_ n, params p
           WHERE n.machine_id = m.machine_id AND n.part_id IS NULL
             AND n.tsp >= p.t0 AND n.tsp < p.t1)                                 AS without_part_id
  FROM machines m LEFT JOIN in_range x USING (machine_id)
  GROUP BY m.machine_id
)
SELECT machine_id, first_passes, later_passes, repeat_passes, unknown_results, without_part_id,
       good_first::numeric    / NULLIF(first_passes, 0) AS first_pass_yield,
       scrap_first::numeric   / NULLIF(first_passes, 0) AS first_pass_scrap_share,
       rework_first::numeric  / NULLIF(first_passes, 0) AS first_pass_rework_share,
       finally_good::numeric  / NULLIF(first_passes, 0) AS final_yield,
       scrap_passes::numeric  / NULLIF(passes, 0)       AS scrap_ratio,
       rework_passes::numeric / NULLIF(passes, 0)       AS rework_ratio
FROM per_machine;
```

- Pooled: sum the counts of `per_machine`, then divide.
- A machine without part rows has every ratio NULL ("no parts"), never 0%.
- Checked: M1 with eight first passes in the range (4 good, 1 scrap, 2
  rework, 1 without a result), a part whose first pass was the day before
  and whose second pass is in the range, a part reworked twice and then
  scrapped: FPY 4/7 = 57.1%, first-pass scrap share 14.3%, rework share
  28.6%, final yield 5/7 = 71.4%, 4 later passes, scrap ratio 2/11 = 18.2%,
  rework ratio 3/11 = 27.3%; M2 FPY 2/3; pooled FPY 6/10 = 60.0% (mean of
  the machines 61.9%). Naive on M1: good rows / rows 50.0%, parts with any
  good row 66.7%, first pass looked for only inside the range 62.5%. With
  a duplicated row, three rows without a part id and a good part tested
  three times: the duplicate counts once, the three are counted apart, the
  two repeat tests are left out (scrap ratio 3/12 = 25.0%, not 3/14).

## Scrap ratio from good and scrap counters

Run the counter pattern of `machine-data-sql.md` once per counter: a key
that holds the counter and the machine keeps the resets of each apart. Put
this CTE first (`quality_counters` holds `tsp, machine_id, kind, counter`,
with `kind` good or scrap), then the core pattern unchanged from `params` to
`judged`, then the rest:

```sql
part_counter AS (
  SELECT tsp, kind || ':' || machine_id AS machine_id, counter FROM quality_counters
),
```

```sql
counted AS (
  SELECT machine_id,
         sum(CASE verdict WHEN 'count' THEN counter - prev
                          WHEN 'rollover' THEN counter + 65536 - prev ELSE 0 END) AS parts_low,
         sum(CASE verdict WHEN 'count' THEN counter - prev
                          WHEN 'rollover' THEN counter + 65536 - prev
                          WHEN 'implausible' THEN counter - prev
                          WHEN 'jitter' THEN 0 ELSE counter END) AS parts_high
  FROM judged GROUP BY machine_id
),
pairs AS (      -- the key is kind:machine, so a machine id may hold ':' itself
  SELECT substr(machine_id, strpos(machine_id, ':') + 1) AS machine_id,
         max(parts_low)  FILTER (WHERE split_part(machine_id, ':', 1) = 'good')  AS good_low,
         max(parts_high) FILTER (WHERE split_part(machine_id, ':', 1) = 'good')  AS good_high,
         max(parts_low)  FILTER (WHERE split_part(machine_id, ':', 1) = 'scrap') AS scrap_low,
         max(parts_high) FILTER (WHERE split_part(machine_id, ':', 1) = 'scrap') AS scrap_high
  FROM counted GROUP BY 1
)
SELECT machine_id, good_low, good_high, scrap_low, scrap_high,
       scrap_low::numeric  / NULLIF(good_high + scrap_low, 0) AS scrap_ratio_lowest,
       scrap_high::numeric / NULLIF(good_low + scrap_high, 0) AS scrap_ratio_highest
FROM pairs;
```

- When the two ratios differ, report the range and ask about the flagged
  steps, as the core says for counts. Counters count every part made, so
  this is the scrap ratio over produced quantity; it is counted over the
  period, not clipped to planned windows (join the steps to `calendar` for
  that). Without a scrap counter the ratio is NULL.
- Checked: M1's good counter reset to 0 and its scrap counter reset to 2 at
  10:05: good 350, scrap 18 to 20, scrap ratio 4.9% to 5.4%; maximum minus
  minimum gives good 1180 and scrap 58 (4.7%), last minus first a negative
  count. M2's counters did not move: NULL, not 0%. A machine id `L1:M7`
  stays whole.

## Checks

Before the figures, continue from `stop_classes`: a class given to a state
that `kinds` does not map as a stop, and a stop without a class, block the
figures. Any row is to be fixed in the mapping or asked about:

```sql
SELECT sc.state, 'has a class but is not a stop in kinds' AS problem
FROM stop_classes sc LEFT JOIN kinds k USING (state)
WHERE k.kind IS DISTINCT FROM 'stop'
UNION ALL
SELECT DISTINCT x.state, 'a stop without a class'
FROM pieces x
WHERE x.kind = 'stop' AND x.state NOT IN (SELECT state FROM stop_classes);
```

Two different results for one part at one time (continue from `rows_` of
the part results):

```sql
SELECT machine_id, part_id, tsp, array_agg(DISTINCT outcome) AS outcomes
FROM rows_ GROUP BY machine_id, part_id, tsp HAVING count(DISTINCT outcome) > 1;
```
