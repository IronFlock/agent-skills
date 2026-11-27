# Energy figures from meter data in SQL

This file shows how energy, load profiles, peaks, base load, energy by
machine state and a baseline are derived from meter rows in PostgreSQL, and
which mistakes each pattern avoids. The definitions are in
`energy-performance.md`; machine states, part counters and planned time are
in `machine-data-sql.md`, whose conventions hold here: example names
(`energy_counter`, `power_readings`, time column `tsp`), the plant's time
zone (`Europe/Berlin` here) in every result, `numeric` before dividing, and
absent is not zero.

## Shapes of meter data

- **Energy counter**: a cumulative reading in kWh (or Wh, or pulses).
  Energy is the difference of readings. It resets (meter exchange, a logger
  restart) and wraps at the width of its register.
- **Power readings**: kW at a moment, or the mean of the interval before the
  reading; the meter's documentation says which. Energy is power integrated
  over time. Never sum or average power values to get energy.
- **Direction**: a meter with feed-in (solar, regenerative drives) reads
  negative power, or a net counter falls. Ask; use separate import
  and export registers where they exist, and never report net as consumption.
- Gas, compressed air, water and heat meters are counters too, in their own
  units.

Before computing, read a sample of rows per meter: the unit, the usual
interval, whether readings fall or go negative, and which machines a meter
feeds. Ask for the unit, the factor, the register's width and the most the
meter can draw (`max_kw`: its rating or the connection) when the column
descriptions do not give them.

## Energy from a counter

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 00:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-19 03:00 Europe/Berlin') AS t1,
         interval '2 hours'    AS margin,     -- readings read before t0 and after t1
         interval '20 minutes' AS meter_gap,  -- readings every 15 minutes: a longer step spans a gap
         1.0      AS factor,      -- kWh per unit of the reading: 0.001 for Wh, times a transformer ratio
         0.1      AS resolution,  -- the meter's last digit in kWh
         100000.0 AS width,       -- the register wraps here, in units of the reading; NULL if not known
         200.0    AS max_kw       -- the most this meter can draw; NULL if not known
),
readings AS (   -- NULL readings ignored; equal time stamps: the lowest reading
  SELECT DISTINCT ON (c.meter_id, c.tsp) c.meter_id, c.tsp, c.reading * p.factor AS kwh
  FROM energy_counter c, params p
  WHERE c.reading IS NOT NULL AND c.tsp >= p.t0 - p.margin AND c.tsp < p.t1 + p.margin
  ORDER BY c.meter_id, c.tsp, c.reading
),
sized AS (      -- each step: its rise, its value if the register wrapped, its hours
  SELECT s.meter_id, s.tsp, s.prev_tsp, s.kwh, s.prev, s.kwh - s.prev AS rise,
         s.kwh + p.width * p.factor - s.prev AS as_wrap,
         extract(epoch FROM s.tsp - s.prev_tsp) / 3600 AS hours,
         s.tsp - s.prev_tsp > p.meter_gap AS spans_gap
  FROM (SELECT r.*, lag(r.kwh) OVER w AS prev, lag(r.tsp) OVER w AS prev_tsp
        FROM readings r WINDOW w AS (PARTITION BY r.meter_id ORDER BY r.tsp)) s, params p
  WHERE s.prev IS NOT NULL
),
limits AS (     -- max_kw; without it ten times the meter's usual high load (90th percentile of 10+ steps)
  SELECT m.meter_id, p.max_kw IS NULL AS from_data,
         coalesce(p.max_kw, CASE WHEN u.n >= 10 AND u.p90 > 0 THEN 10 * u.p90 END) AS limit_kw
  FROM (SELECT DISTINCT meter_id FROM sized) m CROSS JOIN params p
  LEFT JOIN (SELECT meter_id, count(*) AS n, percentile_cont(0.9) WITHIN GROUP (ORDER BY rise / hours) AS p90
             FROM sized WHERE rise >= 0 AND NOT spans_gap GROUP BY meter_id) u USING (meter_id)
),
judged AS (     -- every step that overlaps the range
  SELECT s.*, l.limit_kw, l.from_data,
         extract(epoch FROM least(s.tsp, p.t1) - greatest(s.prev_tsp, p.t0)) / 3600 / s.hours AS share,
         CASE WHEN s.rise >= 0 THEN
                CASE WHEN (s.rise - p.resolution) / s.hours > l.limit_kw THEN 'implausible' ELSE 'count' END
              WHEN -s.rise < p.resolution THEN 'jitter'
              WHEN s.as_wrap IS NOT NULL AND (s.spans_gap OR l.limit_kw IS NULL) THEN 'fall'  -- wrap or reset
              WHEN (s.as_wrap - p.resolution) / s.hours <= l.limit_kw THEN 'rollover'
              WHEN s.kwh < 0.5 * s.prev THEN 'reset'
              ELSE 'decrease' END AS verdict,                                -- a correction, or a net counter
         p.width IS NOT NULL
           AND coalesce(l.limit_kw * s.hours >= p.width * p.factor, s.spans_gap) AS may_hide_wraps
  FROM sized s JOIN limits l USING (meter_id), params p
  WHERE s.tsp > p.t0 AND s.prev_tsp < p.t1
),
energy AS (
  SELECT j.*, j.share * v.low AS kwh_low,
         j.share * (v.high + CASE WHEN j.may_hide_wraps          -- NULL without a limit: no upper bound
                                  THEN greatest(0, floor((j.limit_kw * j.hours - v.high) / (p.width * p.factor)))
                                       * p.width * p.factor ELSE 0 END)
           + CASE WHEN j.limit_kw IS NULL THEN NULL ELSE 0 END AS kwh_high
  FROM judged j CROSS JOIN params p
  CROSS JOIN LATERAL (
    SELECT CASE j.verdict WHEN 'count' THEN j.rise WHEN 'rollover' THEN j.as_wrap ELSE 0 END AS low,
           CASE j.verdict WHEN 'count' THEN j.rise WHEN 'rollover' THEN j.as_wrap
                          WHEN 'implausible' THEN j.rise WHEN 'jitter' THEN 0
                          WHEN 'fall' THEN greatest(j.kwh, j.as_wrap)
                          ELSE j.kwh END AS high) v                  -- reset, decrease: as a reset to 0
),
levels AS (     -- the usual step power between breaks (a fall or a gap): a change of scale shows at a break
  SELECT meter_id, segment, percentile_cont(0.5) WITHIN GROUP (ORDER BY rise / hours) AS median_kw
  FROM (SELECT e.*, sum(CASE WHEN e.spans_gap OR (e.rise < 0 AND e.verdict <> 'jitter') THEN 1 ELSE 0 END)
                      OVER (PARTITION BY e.meter_id ORDER BY e.tsp) AS segment
        FROM energy e) x
  WHERE rise > 0 AND NOT spans_gap
  GROUP BY meter_id, segment HAVING count(*) >= 2
),
jumps AS (      -- the largest ratio between the levels on both sides of a break
  SELECT meter_id, max(greatest(median_kw / prev_kw, prev_kw / median_kw)) AS scale_jump
  FROM (SELECT l.*, lag(l.median_kw) OVER (PARTITION BY l.meter_id ORDER BY l.segment) AS prev_kw FROM levels l) y
  WHERE prev_kw > 0 AND median_kw > 0
  GROUP BY meter_id
)
SELECT e.meter_id, sum(e.kwh_low) AS kwh_low,
       CASE WHEN bool_and(e.kwh_high IS NOT NULL) THEN sum(e.kwh_high) END AS kwh_high,
       coalesce(sum(e.kwh_low) FILTER (WHERE e.spans_gap), 0) AS kwh_across_gaps,
       count(*) FILTER (WHERE e.verdict IN ('reset', 'decrease', 'fall', 'implausible')
                           OR e.may_hide_wraps) AS flagged_steps,
       min(e.prev_tsp) <= p.t0 AND max(e.tsp) >= p.t1
         AND NOT bool_or(e.spans_gap AND e.share < 1) AS complete,
       min(e.limit_kw) AS limit_kw, bool_or(e.from_data) AS limit_from_data, j.scale_jump
FROM energy e CROSS JOIN params p LEFT JOIN jumps j ON j.meter_id = e.meter_id
GROUP BY e.meter_id, p.t0, p.t1, j.scale_jump;
```

- Flagged steps are counted both ways, as for part counters: `kwh_low`
  without them, `kwh_high` with them (a reset as a reset to 0, a jump above
  the limit as counted, a fall that may be a wrap as the larger value, a
  gap as the most wraps the limit allows). When the two differ, report the
  range, list the flagged steps with time and readings, and ask (a meter
  exchange, a logger restart, a wrong reading). `kwh_high` NULL means no
  upper bound: ask for `max_kw`. Never take the maximum minus the minimum.
- Every fall is checked as a wrap of the register: accepted when the wrap's
  energy fits the limit, else flagged. Several small `decrease` steps mean a
  correction or a net counter (import minus export): ask.
- A fall across a gap is never taken as a wrap (a logger restart or a
  meter exchange looks the same): it is flagged.
- `limit_kw` comes from `max_kw`; without it, from the data
  (`limit_from_data`), which catches single gross errors only. With
  `limit_kw` NULL the check did not run and `kwh_high` is NULL: report
  `kwh_low` as "at least" and say so. A wrong `max_kw` flags every step.
- `scale_jump` above about 100 is a warning: the usual step power changed
  by that factor at a fall or a gap, as when a meter is replaced by one
  counting in Wh or a factor changes; the limit from the data then follows
  the wrong scale. Report no energy until the user confirms the unit or
  gives `max_kw`. A machine that idles does not trip it, unless a gap
  separates a shift from a night of standby: look at the readings around
  the break. A change of scale without a fall or a gap is not seen; only
  `max_kw` catches it (its steps are then implausible).
- A step that crosses t0 or t1 gives the range its share by time, as if the
  power were constant within the step. Readings at the range's edges make
  this exact.
- A step across a gap keeps its energy (a counter misses none), unless the
  register could have wrapped in it (flagged). Across an edge, the split is
  unknown and `complete` is false; so it is when the readings begin after
  t0 or end before t1. A meter without a step in the range has no row:
  name it as "no data".

## Energy from power readings

```sql
WITH params AS (
  SELECT timestamptz '2026-11-19 08:00 Europe/Berlin' AS t0,
         least(now(), timestamptz '2026-11-19 10:00 Europe/Berlin') AS t1,
         interval '20 minutes' AS meter_gap,  -- about twice the usual interval
         1.0   AS factor,                     -- kW per unit of the reading: 0.001 for W
         200.0 AS max_kw                      -- the most this meter can see; NULL if not known
),
samples AS (    -- NULL readings ignored; equal time stamps: the lowest reading
  SELECT DISTINCT ON (r.meter_id, r.tsp) r.meter_id, r.tsp, r.power * p.factor AS kw
  FROM power_readings r, params p
  WHERE r.power IS NOT NULL AND r.tsp >= p.t0 - p.meter_gap AND r.tsp < p.t1 + p.meter_gap
  ORDER BY r.meter_id, r.tsp, r.power
),
limits AS (     -- max_kw; without it ten times the usual high reading (90th percentile of 10+)
  SELECT m.meter_id, p.max_kw IS NULL AS limit_from_data,
         coalesce(p.max_kw, CASE WHEN u.n >= 10 AND u.p90 > 0 THEN 10 * u.p90 END) AS limit_kw
  FROM (SELECT DISTINCT meter_id FROM samples) m CROSS JOIN params p
  LEFT JOIN (SELECT meter_id, count(*) AS n, percentile_cont(0.9) WITHIN GROUP (ORDER BY abs(kw)) AS p90
             FROM samples GROUP BY meter_id) u USING (meter_id)
),
power_pieces AS (   -- a reading holds until the next one, at most meter_gap; above the limit: kw NULL
  SELECT * FROM (
    SELECT s.meter_id, CASE WHEN abs(s.kw) > l.limit_kw THEN NULL ELSE s.kw END AS kw,
           false AS from_counter, l.limit_kw, l.limit_from_data, greatest(s.tsp, p.t0) AS t_start,
           least(lead(s.tsp) OVER w, s.tsp + p.meter_gap, p.t1) AS t_end
    FROM samples s JOIN limits l USING (meter_id), params p
    WINDOW w AS (PARTITION BY s.meter_id ORDER BY s.tsp)
  ) x WHERE t_end > t_start
),
power_jumps AS (    -- the usual power between gaps in the readings: a change of scale shows at a gap
  SELECT meter_id, max(greatest(median_kw / prev_kw, prev_kw / median_kw)) AS scale_jump
  FROM (SELECT meter_id, segment, median_kw, lag(median_kw) OVER (PARTITION BY meter_id ORDER BY segment) AS prev_kw
        FROM (SELECT meter_id, segment, percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(kw)) AS median_kw
              FROM (SELECT meter_id, kw, sum(gap) OVER (PARTITION BY meter_id ORDER BY tsp) AS segment
                    FROM (SELECT s.*, CASE WHEN s.tsp - lag(s.tsp) OVER (PARTITION BY s.meter_id ORDER BY s.tsp)
                                                > p.meter_gap THEN 1 ELSE 0 END AS gap
                          FROM samples s, params p) g) z
              GROUP BY meter_id, segment HAVING count(*) >= 2) y) l
  WHERE prev_kw > 0 AND median_kw > 0
  GROUP BY meter_id
)
SELECT x.meter_id,
       coalesce(sum(greatest(x.kw, 0) * extract(epoch FROM x.t_end - x.t_start)) FILTER (WHERE x.kw IS NOT NULL), 0)
         / 3600 AS kwh_import,
       coalesce(sum(greatest(-x.kw, 0) * extract(epoch FROM x.t_end - x.t_start)) FILTER (WHERE x.kw IS NOT NULL), 0)
         / 3600 AS kwh_export,
       coalesce(sum(extract(epoch FROM x.t_end - x.t_start)) FILTER (WHERE x.kw IS NOT NULL), 0) AS metered_s,
       (SELECT extract(epoch FROM t1 - t0) FROM params)
         - coalesce(sum(extract(epoch FROM x.t_end - x.t_start)) FILTER (WHERE x.kw IS NOT NULL), 0) AS no_data_s,
       count(*) FILTER (WHERE x.kw IS NULL) AS readings_above_limit,
       l.limit_kw, l.limit_from_data, j.scale_jump
FROM power_pieces x JOIN limits l USING (meter_id) LEFT JOIN power_jumps j USING (meter_id)
GROUP BY x.meter_id, l.limit_kw, l.limit_from_data, j.scale_jump;
```

- Each reading counts for the time it stands for, so uneven intervals are
  weighted right. `no_data` is time without usable readings: the energy in
  it is unknown. Report it; never scale the energy up silently.
- A reading above the limit is left out (`kw` NULL, its time no data);
  list such readings. `scale_jump` is the same warning as for counters, at
  gaps in the readings. Negative power is export, kept apart from import.
- For a meter whose reading is the mean of the interval before it, a
  reading stands for the time back to the previous one (where a counter
  exists beside the power readings, its total shows which variant fits):

```sql
power_pieces AS (   -- variant: a reading is the mean of the interval before it
  SELECT * FROM (
    SELECT s.meter_id, CASE WHEN abs(s.kw) > l.limit_kw THEN NULL ELSE s.kw END AS kw,
           false AS from_counter, l.limit_kw, l.limit_from_data,
           greatest(lag(s.tsp) OVER w, s.tsp - p.meter_gap, p.t0) AS t_start,
           least(s.tsp, p.t1) AS t_end
    FROM samples s JOIN limits l USING (meter_id), params p
    WINDOW w AS (PARTITION BY s.meter_id ORDER BY s.tsp)
  ) x WHERE t_end > t_start
)
```

- From a counter, the same pieces come from its steps (continue from
  `judged` above), each step at its mean power over its whole interval; a
  flagged step is a piece without power, a step across a gap is no piece:

```sql
power_pieces AS (   -- from an energy counter
  SELECT meter_id,
         CASE verdict WHEN 'count' THEN rise / hours WHEN 'rollover' THEN as_wrap / hours
                      WHEN 'jitter' THEN 0 END AS kw,
         true AS from_counter, limit_kw, from_data AS limit_from_data, prev_tsp AS t_start, tsp AS t_end
  FROM judged
  WHERE NOT spans_gap AND NOT may_hide_wraps
)
```

The patterns for days, the profile, base load and machine states continue
from `power_pieces`, count import only (`greatest(kw, 0)`) and treat a
piece without power (`kw` NULL) as no data.

## Energy per day, and gaps

Days in the plant's zone: the day the clocks change has 23 or 25 hours.

```sql
day_windows AS (
  SELECT d::date AS day,
         d::date::timestamp AT TIME ZONE 'Europe/Berlin'       AS d_start,
         (d::date + 1)::timestamp AT TIME ZONE 'Europe/Berlin' AS d_end
  FROM generate_series(date '2026-10-25', date '2026-10-27', interval '1 day') AS d
),
daily AS (
  SELECT w.day, m.meter_id, extract(epoch FROM w.d_end - w.d_start) AS day_s,
         coalesce(sum(greatest(e.kw, 0) * extract(epoch FROM least(e.t_end, w.d_end) - greatest(e.t_start, w.d_start)))
                  FILTER (WHERE e.kw IS NOT NULL), 0) / 3600 AS kwh_known,
         coalesce(sum(extract(epoch FROM least(e.t_end, w.d_end) - greatest(e.t_start, w.d_start)))
                  FILTER (WHERE e.kw IS NOT NULL), 0) AS metered_s   -- least() skips NULLs
  FROM day_windows w CROSS JOIN (SELECT DISTINCT meter_id FROM power_pieces) m
  LEFT JOIN power_pieces e ON e.meter_id = m.meter_id AND e.t_start < w.d_end AND e.t_end > w.d_start
  GROUP BY w.day, m.meter_id, w.d_start, w.d_end
)
SELECT day, meter_id, CASE WHEN metered_s > day_s - 1 THEN kwh_known END AS kwh,
       kwh_known, day_s - metered_s AS missing_s
FROM daily ORDER BY meter_id, day;
```

- A day with missing time has no energy (`kwh` NULL); `kwh_known` and
  `missing_s` say how much is known. Never fill a gap with zero, the last
  value or a line. An estimate (the mean power of the same hours on other
  days) only when the user agrees, named as an estimate.
- With a counter, take each day as the range of the counter pattern
  instead: a gap inside the day leaves the day's total exact.

## The load profile and the peak

The window length and its alignment come from the user's contract: ask.
Many tariffs, Germany's registering load metering among them, bill the
highest mean over a clock quarter hour; others use 30 or 60 minutes, a
rolling window, or kVA, which this pattern does not compute. t0 must lie
on a window edge.

```sql
windows AS (    -- the contract's billing window, 15 minutes here
  SELECT m.meter_id, m.limit_kw, m.limit_from_data, w AS w_start, w + l.len AS w_end,
         extract(epoch FROM l.len) AS len_s
  FROM (SELECT meter_id, max(limit_kw) AS limit_kw, bool_or(limit_from_data) AS limit_from_data
        FROM power_pieces GROUP BY meter_id) m,
       (SELECT interval '15 minutes' AS len) l, params p,
       generate_series(p.t0, p.t1 - l.len, l.len) AS w
),
profile AS (
  SELECT w.meter_id, w.w_start, w.len_s, w.limit_kw, w.limit_from_data,
         coalesce(sum(greatest(x.kw, 0) * extract(epoch FROM least(x.t_end, w.w_end) - greatest(x.t_start, w.w_start)))
                  FILTER (WHERE x.kw IS NOT NULL), 0) / 3600 AS kwh,
         coalesce(sum(extract(epoch FROM least(x.t_end, w.w_end) - greatest(x.t_start, w.w_start)))
                  FILTER (WHERE x.kw IS NOT NULL), 0) AS covered_s,   -- least() skips NULLs
         count(x.t_start) FILTER (WHERE x.kw IS NULL) AS removed,
         coalesce(bool_or(x.from_counter AND (x.t_start < w.w_start OR x.t_end > w.w_end)), false) AS smoothed
  FROM windows w LEFT JOIN power_pieces x
    ON x.meter_id = w.meter_id AND x.t_start < w.w_end AND x.t_end > w.w_start
  GROUP BY w.meter_id, w.w_start, w.len_s, w.limit_kw, w.limit_from_data
),
bounds AS (     -- each window's mean power: the known part (low) and the most it can be (high)
  SELECT f.*, f.kwh * 3600 / f.len_s AS low_kw,
         CASE WHEN f.smoothed OR (f.removed > 0 AND f.limit_from_data) THEN NULL
              WHEN f.covered_s > f.len_s - 1 THEN f.kwh * 3600 / f.len_s
              ELSE (f.kwh * 3600 + (f.len_s - f.covered_s) * f.limit_kw) / f.len_s END AS high_kw
  FROM profile f
)
SELECT meter_id,
       max(low_kw) AS peak_low_kw,
       CASE WHEN bool_and(high_kw IS NOT NULL) THEN max(high_kw) END AS peak_high_kw,
       (array_agg(w_start ORDER BY low_kw DESC, w_start))[1] AT TIME ZONE 'Europe/Berlin' AS peak_at,
       (array_agg(w_start ORDER BY low_kw DESC, w_start))[1] AS peak_start,     -- unambiguous
       count(*) FILTER (WHERE covered_s <= len_s - 1) AS incomplete_windows,
       sum(removed) AS removed_readings,
       count(*) FILTER (WHERE smoothed) AS smoothed_windows
FROM bounds GROUP BY meter_id;
```

- The peak is the highest mean over a whole window: not the highest
  reading. When `peak_low_kw` equals `peak_high_kw`, it is known. Else
  report the range, or "at least `peak_low_kw`" when `peak_high_kw` is
  NULL, and say why: missing time (bounded by `limit_kw`), readings removed
  by a limit taken from the data (never bounded: they may be a real
  start-up), or `smoothed` windows (counter readings off the window edges
  spread each step evenly: a true 400 kW can show as 250 kW).
- `peak_at` is plant time; on the night the clocks go back it is
  ambiguous, `peak_start` is not.
- The billed peak is that of the connection. `site_meters` lists the main
  meter, or meters of which none is behind another (ask); summing a main
  meter with its submeters counts their load twice. Add their energy per
  window, then take the maximum: the sum of each meter's own peak is too
  high, because peaks fall at different times.

```sql
SELECT w_start AT TIME ZONE 'Europe/Berlin' AS window_start, w_start, sum(kwh) * 3600 / min(len_s) AS site_kw,
       count(*) = (SELECT count(*) FROM site_meters) AND bool_and(covered_s > len_s - 1) AS complete,
       bool_or(smoothed) AS smoothed
FROM profile WHERE meter_id IN (SELECT meter_id FROM site_meters)
GROUP BY w_start ORDER BY site_kw DESC LIMIT 5;
```

## Base load

```sql
SELECT f.meter_id,
       percentile_cont(0.05) WITHIN GROUP (ORDER BY f.kwh * 3600 / f.len_s) AS p05_kw,
       CASE WHEN (SELECT min(production_day) FROM calendar) < min((f.w_start AT TIME ZONE 'Europe/Berlin')::date)
             AND (SELECT max(production_day) FROM calendar) >= max((f.w_start AT TIME ZONE 'Europe/Berlin')::date)
            THEN percentile_cont(0.5) WITHIN GROUP (ORDER BY f.kwh * 3600 / f.len_s) FILTER (WHERE NOT EXISTS (
                   SELECT 1 FROM calendar c WHERE c.sign = 1
                     AND c.w_start < f.w_start + f.len_s * interval '1 second' AND c.w_end > f.w_start))
       END AS outside_plan_kw,
       count(*) AS windows
FROM profile f WHERE f.covered_s > f.len_s - 1
GROUP BY f.meter_id;
```

- `calendar` is the plan of `machine-data-sql.md` ("Planned production
  time"). It must cover every day of the profile and the day before (a
  night shift reaches into the next morning), else `outside_plan_kw` is
  NULL: a day missing from the plan would count as unplanned.
- `outside_plan_kw` is the median power while nothing is planned (nights,
  weekends): what stays on. `p05_kw` needs no plan. Name the method, the
  period, and that only whole windows count. Energy of the base load = base
  load x hours: name it as that product.

## Energy by machine state

Add `meter_gap`, `factor` and `max_kw` to the `params` of the base query of
`machine-data-sql.md`, then `samples`, `limits` and `power_pieces` from
above. `meters` maps each meter to the one machine it feeds alone (ask;
never guess it from names); a machine may have several meters.

```sql
by_meter AS (
  SELECT x.machine_id, x.state, x.kind, m.meter_id,
         sum(greatest(e.kw, 0) * extract(epoch FROM least(x.t_end, e.t_end, p.t1) - greatest(x.t_start, e.t_start, p.t0)))
           / 3600 AS kwh,
         sum(extract(epoch FROM least(x.t_end, e.t_end, p.t1) - greatest(x.t_start, e.t_start, p.t0))) AS metered_s
  FROM pieces x
  JOIN meters m ON m.machine_id = x.machine_id
  JOIN power_pieces e ON e.meter_id = m.meter_id AND e.kw IS NOT NULL
                      AND e.t_start < x.t_end AND e.t_end > x.t_start,
       params p
  WHERE least(x.t_end, e.t_end, p.t1) > greatest(x.t_start, e.t_start, p.t0)
  GROUP BY x.machine_id, x.state, x.kind, m.meter_id
),
by_state AS (   -- several meters of one machine: energies and mean powers add up
  SELECT machine_id, state, kind, sum(kwh) AS kwh, min(metered_s) AS metered_s,
         sum(kwh * 3600 / metered_s) AS mean_kw, count(*) AS meters_seen
  FROM by_meter GROUP BY machine_id, state, kind
),
state_time AS (
  SELECT x.machine_id, x.state,
         sum(extract(epoch FROM least(x.t_end, p.t1) - greatest(x.t_start, p.t0))) AS state_s
  FROM pieces x, params p WHERE x.t_end > p.t0 AND x.t_start < p.t1
  GROUP BY x.machine_id, x.state
)
SELECT t.machine_id, t.state, b.kind, t.state_s, b.metered_s, b.kwh, b.mean_kw, b.meters_seen,
       (SELECT count(*) FROM meters m WHERE m.machine_id = t.machine_id) AS meters_mapped
FROM state_time t LEFT JOIN by_state b USING (machine_id, state)
ORDER BY t.machine_id, b.kwh DESC NULLS LAST;
```

- Group by the state value: waiting, a fault, a break and switched off
  draw different power, and that difference is the finding.
- `metered_s` below `state_s`, or `meters_seen` below `meters_mapped`,
  means meter data is missing in that state; the mean power then covers the
  metered part only. Energy outside any state piece is the meter's total
  minus the sum here: report it.
- With counter pieces, a state shorter than the reading interval gets an
  average, not its own power: say so when states change faster than the
  meter reads.

## Energy per good part, pooled

```sql
WITH per_group(meter_group, kwh, good) AS (   -- one row per meter, or group of meters, and what it feeds alone
  VALUES ('A', 700.0, 1000), ('B', 400.0, 400), ('C', NULL, 300), ('D', 50.0, 0)
)
SELECT sum(kwh) FILTER (WHERE kwh IS NOT NULL AND good IS NOT NULL)
         / NULLIF(sum(good) FILTER (WHERE kwh IS NOT NULL AND good IS NOT NULL), 0) AS kwh_per_good_part,
       sum(kwh) FILTER (WHERE kwh IS NOT NULL AND good IS NOT NULL) AS kwh,
       sum(good) FILTER (WHERE kwh IS NOT NULL AND good IS NOT NULL) AS good,
       string_agg(meter_group, ', ') FILTER (WHERE kwh IS NULL OR good IS NULL) AS left_out
FROM per_group;
```

- Energy and parts cover the same range: all good parts made in it, not
  only those inside the planned windows and known states, unless the energy
  is clipped to the same windows. A meter that feeds several machines is
  one row with all their parts; never its kWh on each machine.
- Sum energy and sum parts, then divide: 1,150 kWh / 1,400 parts = 0.821
  kWh per part here, with C named as left out beside it. The average of the
  ratios (0.85) is wrong, and so is counting the parts of C (0.676).
- D made no parts and still drew energy: its own ratio is not computable,
  its energy counts in the pool.
- Sum parts only over machines side by side on the same product; a line in
  series is divided by the parts at its end.

## Baseline and cumulative difference

One row per day (or week): energy of a complete day (above), output of the
same day, and whether the day is complete. The periods come from the user;
the baseline needs at least 30 complete periods, better a year.

```sql
WITH params AS (
  SELECT date '2026-09-01' AS base_from, date '2026-10-04' AS base_to,
         date '2026-10-14' AS report_from, date '2026-10-20' AS report_to
),
model AS (      -- energy = a + b x output, fitted on the complete days of the baseline period
  SELECT regr_intercept(kwh, output) AS a, regr_slope(kwh, output) AS b,
         regr_r2(kwh, output) AS r2, regr_count(kwh, output) AS n,
         regr_avgx(kwh, output) AS x_mean, regr_sxx(kwh, output) AS sxx,
         min(output) AS x_min, max(output) AS x_max,
         sqrt(regr_syy(kwh, output) * (1 - regr_r2(kwh, output))
              / NULLIF(regr_count(kwh, output) - 2, 0)) AS s     -- residual standard error, kWh per day
  FROM daily_figures, params p
  WHERE complete AND day >= p.base_from AND day < p.base_to
),
dependence AS (   -- lag-1 autocorrelation of the baseline's residuals
  SELECT sum(e * prev_e) / NULLIF(sum(e * e), 0) AS r
  FROM (SELECT d.kwh - (m.a + m.b * d.output) AS e,
               lag(d.kwh - (m.a + m.b * d.output)) OVER (ORDER BY d.day) AS prev_e
        FROM daily_figures d, model m, params p
        WHERE d.complete AND d.day >= p.base_from AND d.day < p.base_to) x
),
compared AS (
  SELECT d.day, d.output, d.kwh, m.a + m.b * d.output AS expected,
         d.kwh - (m.a + m.b * d.output) AS difference,
         d.output BETWEEN m.x_min AND m.x_max AS in_range
  FROM daily_figures d, model m, params p
  WHERE d.complete AND d.day >= p.report_from AND d.day < p.report_to
)
SELECT day, output, kwh, expected, difference, in_range,
       sum(difference) FILTER (WHERE in_range) OVER (ORDER BY day) AS cumulative_difference
FROM compared ORDER BY day;
```

The total, its uncertainty, and the days left out (continue from
`compared`):

```sql
totals AS (
  SELECT count(*) FILTER (WHERE in_range) AS k, sum(output) FILTER (WHERE in_range) AS sum_x,
         sum(expected) FILTER (WHERE in_range) AS expected_kwh,
         sum(difference) FILTER (WHERE in_range) AS total_difference,
         string_agg(day::text, ', ') FILTER (WHERE NOT in_range) AS outside_baseline_range
  FROM compared
),
t_95(df, t) AS (  -- Student's t, two-sided 95 %; the row with the largest df not above n - 2
  VALUES (8, 2.306), (10, 2.228), (15, 2.131), (20, 2.086), (25, 2.060), (28, 2.048),
         (30, 2.042), (40, 2.021), (60, 2.000), (120, 1.980)
)
SELECT o.k AS days, o.expected_kwh, o.total_difference, d.r, u.se_kwh, u.t * u.se_kwh AS limit_kwh,
       u.decidable, u.decidable AND abs(o.total_difference) > u.t * u.se_kwh AS beyond_noise,
       (SELECT string_agg(day::text, ', ') FROM daily_figures, params p
         WHERE NOT complete AND day >= p.report_from AND day < p.report_to) AS incomplete_days,
       o.outside_baseline_range
FROM totals o, model m, dependence d
CROSS JOIN LATERAL (
  SELECT m.s * sqrt(o.k + o.k::float8 * o.k / m.n + (o.sum_x::float8 - o.k * m.x_mean) ^ 2 / m.sxx)
           * sqrt((1 + greatest(d.r, 0)) / (1 - least(greatest(d.r, 0), 0.9))) AS se_kwh,   -- dependent days
         (SELECT t FROM t_95 WHERE df <= m.n - 2 ORDER BY df DESC LIMIT 1) AS t,
         m.n >= 30 AND coalesce(d.r, 0) <= CASE WHEN m.n < 60 THEN 0.3 ELSE 0.6 END AS decidable) u;
```

- Report the model with it: a (fixed energy per day), b (energy per unit),
  r2, n and the output range it was fitted on.
- A negative difference is less energy than the baseline expects. The
  cumulative difference turns where performance changed; a flat line is
  performance as in the baseline.
- `se_kwh` is the uncertainty of the total: the days' own scatter and the
  fitted line's error, which does not shrink with more reporting days,
  widened by `r`, the dependence of one day's residual on the day before
  (weather, a slow drift). Call a total a saving or an excess only when
  `beyond_noise`, and say how sure that is: wrong about 1 time in 20 with
  independent days, up to about 1 in 12 when days depend on each other;
  never "proven". When not `decidable`, do not compare: with fewer than 30
  periods the baseline is too short; with `r` above 0.3 (below 60 periods)
  or above 0.6, daily figures cannot decide: use weekly periods.
- Days outside the output range of the fit are not compared, and
  incomplete days are left out; list both. More variables (degree days,
  product mix) need a model with several; these aggregates take one.
