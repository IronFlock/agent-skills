# Control charts and capability indices in SQL

This file shows how control limits, run-rule signals and capability indices
are computed from measurements in PostgreSQL with TimescaleDB. What each
chart and index means is in `process-quality.md`. The conventions are those
of `machine-data-sql.md`: table and column names are examples
(`part_measurements` with `tsp, machine_id, part_id, diameter`;
`part_results` with a `result` per part), the time column is `tsp`, the
plant's time zone (`Europe/Berlin` here) is stated in every result, and a
missing input stays NULL and is reported, never replaced.

## Charts, limits and constants

| Data | Chart | Centre and limits |
| --- | --- | --- |
| one value per part | individuals, moving range (I-MR) | mean +/- 2.66 MR-bar; MR up to 3.267 MR-bar |
| subgroups of 2 to 10 | X-bar R | grand mean +/- A2 R-bar; R from D3 R-bar to D4 R-bar |
| subgroups above 10 | X-bar s | grand mean +/- A3 s-bar; s from B3 s-bar to B4 s-bar |
| defective parts of n | p | p-bar +/- 3 sqrt(p-bar (1 - p-bar) / n) |
| defects per unit | u | u-bar +/- 3 sqrt(u-bar / n) |

| n | d2 | d3 | c4 | A2 | D3 | D4 | A3 | B3 | B4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 1.128 | 0.853 | 0.7979 | 1.880 | 0 | 3.267 | 2.659 | 0 | 3.267 |
| 3 | 1.693 | 0.888 | 0.8862 | 1.023 | 0 | 2.574 | 1.954 | 0 | 2.568 |
| 4 | 2.059 | 0.880 | 0.9213 | 0.729 | 0 | 2.282 | 1.628 | 0 | 2.266 |
| 5 | 2.326 | 0.864 | 0.9400 | 0.577 | 0 | 2.114 | 1.427 | 0 | 2.089 |
| 6 | 2.534 | 0.848 | 0.9515 | 0.483 | 0 | 2.004 | 1.287 | 0.030 | 1.970 |
| 7 | 2.704 | 0.833 | 0.9594 | 0.419 | 0.076 | 1.924 | 1.182 | 0.118 | 1.882 |
| 8 | 2.847 | 0.820 | 0.9650 | 0.373 | 0.136 | 1.864 | 1.099 | 0.185 | 1.815 |
| 9 | 2.970 | 0.808 | 0.9693 | 0.337 | 0.184 | 1.816 | 1.032 | 0.239 | 1.761 |
| 10 | 3.078 | 0.797 | 0.9727 | 0.308 | 0.223 | 1.777 | 0.975 | 0.284 | 1.716 |

Above 10, c4 is 4(n - 1) / (4n - 3) (within 0.0003 of the exact value).
A subgroup is a few consecutive parts under the same conditions (one
machine, cavity, spindle, tool, lot); with varying sizes, sigma is the mean
of R / d2(n) and each mean gets grand mean +/- 3 sigma / sqrt(n).

## One value per part or cycle

```sql
SELECT machine_id, cycle_no, min(tsp) AS tsp, max(force) AS x   -- the characteristic: here the peak force
FROM press_readings
WHERE tsp >= timestamptz '2026-11-02 06:00 Europe/Berlin'
  AND tsp <  timestamptz '2026-11-16 06:00 Europe/Berlin'
GROUP BY machine_id, cycle_no;
```

Which value stands for a cycle (peak, mean, final) is the user's
definition; ask. Without a cycle number, cycles come from the state rows
(the run pieces of `machine-data-sql.md`).

## Individual values: limits from a baseline

The baseline is a fixed period the user calls normal; its dates in the
query hold the limits. The chart window is separate: the last days for a
live transform (as below), or a fixed period for a one-off question. Only
the two windows are read; where they touch, they are one sequence.

```sql
WITH params AS (
  SELECT 'P-3'::text AS machine,
         timestamptz '2026-11-02 06:00 Europe/Berlin' AS b0,   -- baseline: fixed dates hold the limits
         timestamptz '2026-11-09 06:00 Europe/Berlin' AS b1,
         now() - interval '7 days' AS t0,                      -- chart window
         now() AS t1,
         25 AS min_values                                      -- fewer in the baseline: no limits
),
excluded(t_from, t_to) AS (     -- baseline points with a known cause, left out with the user's agreement
  VALUES (NULL::timestamptz, NULL::timestamptz)
),
pts AS (        -- one value per part; no measurement: left out
  SELECT m.tsp, m.part_id, m.diameter::numeric AS x, m.tsp >= p.b0 AND m.tsp < p.b1 AS baseline,
         CASE WHEN p.t0 <= p.b1 AND p.t1 >= p.b0 THEN 0      -- the windows touch: one sequence
              WHEN m.tsp >= p.b0 AND m.tsp < p.b1 THEN 1 ELSE 2 END AS seg
  FROM part_measurements m, params p
  WHERE m.machine_id = p.machine AND m.diameter IS NOT NULL
    AND ((m.tsp >= p.b0 AND m.tsp < p.b1) OR (m.tsp >= p.t0 AND m.tsp < p.t1))
    AND NOT EXISTS (SELECT 1 FROM excluded e WHERE m.tsp >= e.t_from AND m.tsp < e.t_to)
),
mr AS (         -- moving ranges along each sequence, never across a gap between the windows
  SELECT *, lag(x) OVER w AS prev, abs(x - lag(x) OVER w) AS mr, lag(baseline) OVER w AS prev_baseline
  FROM pts WINDOW w AS (PARTITION BY seg ORDER BY tsp, part_id)
),
base AS (
  SELECT count(*) AS n, avg(x) AS cl,
         avg(mr) FILTER (WHERE prev_baseline) AS mr_bar,        -- pairs inside the baseline only
         corr(x, prev) FILTER (WHERE prev_baseline) AS r1,      -- lag-1 autocorrelation
         count(DISTINCT x) AS distinct_values, max(x) - min(x) AS spread
  FROM mr WHERE baseline
),
step AS (       -- smallest step between distinct values; float noise (below a millionth of the spread) ignored
  SELECT min(d.x - d.lower_x) FILTER (WHERE d.x - d.lower_x > 1e-6 * b.spread) AS step
  FROM (SELECT x, lag(x) OVER (ORDER BY x) AS lower_x FROM (SELECT DISTINCT x FROM pts WHERE baseline) u) d, base b
),
limits AS (
  SELECT b.*, b.mr_bar / 1.128 AS sigma, 3.267 * b.mr_bar AS mr_ucl,
         floor(3.267 * b.mr_bar / s.step) + 1 AS range_levels,
         CASE WHEN b.n < p.min_values
                THEN 'too few values: ' || b.n || ' in the baseline, at least ' || p.min_values
              WHEN b.mr_bar = 0
                THEN 'no variation in the baseline: a frozen value or a reading too coarse'
              ELSE 'ok' END AS status,
         CASE WHEN b.r1 > greatest(0.3, 3 / sqrt(greatest(b.n, 1)))
                THEN 'autocorrelated (lag-1 ' || round(b.r1::numeric, 2) || '): values too close together, or a drift; limits too narrow'
              WHEN b.r1 < -greatest(0.3, 3 / sqrt(greatest(b.n, 1)))
                THEN 'values alternate (lag-1 ' || round(b.r1::numeric, 2) || '): mixed streams or over-adjustment; chart each stream'
              WHEN floor(3.267 * b.mr_bar / s.step) + 1 <= 4
                THEN 'reading too coarse: ' || (floor(3.267 * b.mr_bar / s.step) + 1) || ' steps under the range limit'
         END AS warning
  FROM base b, step s, params p
)
SELECT * FROM limits;
```

- Report `status` as it is; "too few values" and "no variation" are
  answers. A `warning` comes before any signal: with it the chart's signals
  are not special causes; say what to change.
- The warning thresholds, simulated on stable normal data: lag-1 beyond
  0.3 (from 100 values; 3 / sqrt(n) below): 0.2% of baselines; reading too
  coarse: 0% when the reading's step is half a sigma, 81% when it is one
  sigma (100 values).
- After a gap between the windows, the first chart point has no moving
  range and runs start again.

## Every point against the limits

Continue from `limits`:

```sql
zed AS (
  SELECT row_number() OVER (ORDER BY m.tsp, m.part_id) AS i, m.tsp AS t, m.x, m.baseline, m.seg,
         l.cl - 3 * l.sigma AS lcl, l.cl, l.cl + 3 * l.sigma AS ucl,
         (m.x - l.cl) / l.sigma AS z,
         m.x > m.prev AS rises, m.x < m.prev AS falls,
         m.mr AS spread, 0 AS spread_lcl, l.mr_ucl AS spread_ucl,       -- the moving-range chart
         m.mr > l.mr_ucl AS range_signal
  FROM mr m, limits l WHERE l.status = 'ok'
),
rules AS (
  SELECT *,
    abs(z) > 3 AS rule1,
    (z > 2 AND count(*) FILTER (WHERE z > 2) OVER w3 >= 2)
      OR (z < -2 AND count(*) FILTER (WHERE z < -2) OVER w3 >= 2) AS rule2,
    (z > 1 AND count(*) FILTER (WHERE z > 1) OVER w5 >= 4)
      OR (z < -1 AND count(*) FILTER (WHERE z < -1) OVER w5 >= 4) AS rule3,
    count(*) FILTER (WHERE z > 0) OVER w8 = 8 OR count(*) FILTER (WHERE z < 0) OVER w8 = 8 AS rule4,
    count(*) FILTER (WHERE rises) OVER w5 = 5 OR count(*) FILTER (WHERE falls) OVER w5 = 5 AS trend
  FROM zed
  WINDOW w3 AS (PARTITION BY seg ORDER BY i ROWS 2 PRECEDING),
         w5 AS (PARTITION BY seg ORDER BY i ROWS 4 PRECEDING),
         w8 AS (PARTITION BY seg ORDER BY i ROWS 7 PRECEDING)
)
SELECT t, round(x, 4) AS x, baseline, round(lcl, 4) AS lcl, round(cl, 4) AS cl, round(ucl, 4) AS ucl,
       round(z::numeric, 2) AS z, round(spread, 4) AS spread, round(spread_ucl, 4) AS spread_ucl,
       rule1, rule2, rule3, rule4, trend, range_signal
FROM rules
WHERE rule1 OR rule2 OR rule3 OR rule4 OR trend OR range_signal
ORDER BY i;
```

- The rules: 1 beyond 3; 2 two of the last three beyond 2 on one side, the
  current one among them; 3 four of the last five beyond 1 on one side; 4
  eight in a row on one side (a point on the centre breaks the run); trend
  six in a row rising or falling (equal values break it); and the moving
  range above its limit.
- False alarms, as points until the first one (simulated, known limits):
  rule 1 370, the moving range alone 119, the five rules 77, all six
  together 52.
- Several rule 4 or trend points in a row are a likely change, also when
  the index query accepts their number.

For a board, use this last select instead: one row per part of the chart
window with its limits and the spread chart, `signal_x` NULL except where
the values chart signals, `signal_spread` NULL except where the spread
chart does (a wild part raises two moving ranges; only the part itself is
marked on the values chart).

```sql
SELECT t, x, lcl, cl, ucl, spread, spread_lcl, spread_ucl,
       CASE WHEN rule1 OR rule2 OR rule3 OR rule4 OR trend THEN x END AS signal_x,
       CASE WHEN range_signal THEN spread END AS signal_spread
FROM rules
WHERE NOT baseline
ORDER BY i;
```

## Subgroups: means with ranges or standard deviations

The first five parts of each hour form a subgroup. Parts are numbered
before NULLs are dropped, so a missing measurement makes its subgroup
smaller instead of pulling in the next part.

```sql
WITH params AS (
  SELECT 'P-3'::text AS machine,
         timestamptz '2026-11-02 00:00 Europe/Berlin' AS b0,
         timestamptz '2026-11-02 20:00 Europe/Berlin' AS b1,
         now() - interval '7 days' AS t0,
         now() AS t1,
         5 AS size,               -- parts per subgroup
         20 AS min_subgroups
),
k(n, d2, d3, c4) AS (VALUES (2, 1.128, 0.853, 0.7979), (3, 1.693, 0.888, 0.8862), (4, 2.059, 0.880, 0.9213),
  (5, 2.326, 0.864, 0.9400), (6, 2.534, 0.848, 0.9515), (7, 2.704, 0.833, 0.9594),
  (8, 2.847, 0.820, 0.9650), (9, 2.970, 0.808, 0.9693), (10, 3.078, 0.797, 0.9727)),
parts AS (
  SELECT time_bucket('1 hour', m.tsp, 'Europe/Berlin') AS sg, m.diameter::numeric AS x,
         row_number() OVER (PARTITION BY time_bucket('1 hour', m.tsp, 'Europe/Berlin')
                            ORDER BY m.tsp, m.part_id) AS no_in_sg
  FROM part_measurements m, params p
  WHERE m.machine_id = p.machine
    AND ((m.tsp >= p.b0 AND m.tsp < p.b1) OR (m.tsp >= p.t0 AND m.tsp < p.t1))
),
sub AS (
  SELECT g.*, k.d2, k.d3, coalesce(k.c4, 4.0 * (g.n - 1) / (4 * g.n - 3)) AS c4,
         g.sg >= p.b0 AND g.sg < p.b1 AS baseline,
         CASE WHEN p.t0 <= p.b1 AND p.t1 >= p.b0 THEN 0
              WHEN g.sg >= p.b0 AND g.sg < p.b1 THEN 1 ELSE 2 END AS seg
  FROM (SELECT sg, count(x) AS n, avg(x) AS xbar, max(x) - min(x) AS r, stddev_samp(x) AS s
        FROM parts, params p WHERE no_in_sg <= p.size GROUP BY sg) g
  LEFT JOIN k ON k.n = g.n, params p
  WHERE g.n > 0
),
base AS (
  SELECT count(*) FILTER (WHERE n >= 2) AS m,              -- subgroups with a spread
         sum(n * xbar) / sum(n) AS cl,
         bool_or(n > 10) AS large,                          -- then the s chart throughout
         CASE WHEN bool_or(n > 10) THEN avg(s / c4) FILTER (WHERE n >= 2)
              ELSE avg(r / d2) FILTER (WHERE n >= 2) END AS sigma
  FROM sub WHERE baseline
),
limits AS (
  SELECT b.*, CASE WHEN b.sigma IS NULL
                     THEN 'no subgroup with two or more parts: use the individuals chart'
                   WHEN b.m < p.min_subgroups
                     THEN 'too few subgroups: ' || b.m || ' with two or more parts in the baseline, at least ' || p.min_subgroups
                   WHEN b.sigma = 0 THEN 'no variation in the baseline: a frozen value or a reading too coarse'
                   ELSE 'ok' END AS status
  FROM base b, params p
)
SELECT * FROM limits;
```

Continue from `limits` with this `zed`, then `rules` and either last
select of the individuals chart, unchanged:

```sql
zed AS (
  SELECT row_number() OVER (ORDER BY s.sg) AS i, s.sg AS t, s.n, s.xbar AS x, s.r, s.s, s.baseline, s.seg,
         l.cl - 3 * l.sigma / sqrt(s.n::numeric) AS lcl, l.cl, l.cl + 3 * l.sigma / sqrt(s.n::numeric) AS ucl,
         (s.xbar - l.cl) / (l.sigma / sqrt(s.n::numeric)) AS z,
         s.xbar > lag(s.xbar) OVER w AS rises, s.xbar < lag(s.xbar) OVER w AS falls,
         x.spread, greatest(0, x.lo) AS spread_lcl, x.hi AS spread_ucl,     -- the R or s chart
         x.spread > x.hi OR x.spread < x.lo AS range_signal
  FROM sub s, limits l,
       LATERAL (SELECT CASE WHEN l.large THEN s.s ELSE s.r END AS spread,
                       CASE WHEN l.large THEN (s.c4 - 3 * sqrt(1 - s.c4 ^ 2)) * l.sigma
                            ELSE (s.d2 - 3 * s.d3) * l.sigma END AS lo,
                       CASE WHEN l.large THEN (s.c4 + 3 * sqrt(1 - s.c4 ^ 2)) * l.sigma
                            ELSE (s.d2 + 3 * s.d3) * l.sigma END AS hi) x
  WHERE l.status = 'ok'
  WINDOW w AS (PARTITION BY s.seg ORDER BY s.sg)
),
```

- With complete subgroups, `cl +/- 3 * sigma / sqrt(n)` is grand mean +/-
  A2 x R-bar; the range limits are D3 and D4 x R-bar. A smaller subgroup
  gets wider limits; one of a single part has no spread and is plotted
  against `3 * sigma`. Say how many subgroups were incomplete.
- `large`: some subgroup has more than 10 parts; sigma is then s-bar / c4
  and the spread signal tests s.
- The index query below continues from the individuals chart only; there
  is no verified pattern for an index from subgroups here. Say so.

## Proportion of defective parts, varying sample size

```sql
WITH params AS (
  SELECT 'P-3'::text AS machine,
         timestamptz '2026-11-02 00:00 Europe/Berlin' AS b0,
         timestamptz '2026-11-02 20:00 Europe/Berlin' AS b1,
         now() - interval '7 days' AS t0,
         now() AS t1,
         20 AS min_samples
),
samples AS (    -- a sample: the parts of one hour with a result
  SELECT time_bucket('1 hour', r.tsp, 'Europe/Berlin') AS t, count(*) AS n,
         count(*) FILTER (WHERE r.result <> 'OK') AS d
  FROM part_results r, params p
  WHERE r.machine_id = p.machine AND r.result IS NOT NULL
    AND ((r.tsp >= p.b0 AND r.tsp < p.b1) OR (r.tsp >= p.t0 AND r.tsp < p.t1))
  GROUP BY 1
),
base AS (
  SELECT count(*) AS m, sum(d)::numeric / NULLIF(sum(n), 0) AS pbar
  FROM samples, params p WHERE t >= p.b0 AND t < p.b1
),
limits AS (
  SELECT b.*, CASE WHEN b.m < p.min_samples
                     THEN 'too few samples: ' || b.m || ' in the baseline, at least ' || p.min_samples
                   WHEN b.pbar IN (0, 1) THEN 'no variation in the baseline: every part had the same result'
                   ELSE 'ok' END AS status
  FROM base b, params p
)
SELECT s.t, s.n, s.d, round(s.d::numeric / s.n, 4) AS p, round(l.pbar, 4) AS pbar,
       round(greatest(0, l.pbar - 3 * sqrt(l.pbar * (1 - l.pbar) / s.n)), 4) AS lcl,
       round(l.pbar + 3 * sqrt(l.pbar * (1 - l.pbar) / s.n), 4) AS ucl,
       s.t >= p.b0 AND s.t < p.b1 AS baseline,
       s.d::numeric / s.n > l.pbar + 3 * sqrt(l.pbar * (1 - l.pbar) / s.n)
         OR s.d::numeric / s.n < l.pbar - 3 * sqrt(l.pbar * (1 - l.pbar) / s.n) AS signal
FROM samples s, limits l, params p
WHERE l.status = 'ok'
ORDER BY s.t;
```

- `pbar` is all defectives over all parts of the baseline, never the mean
  of hourly proportions. At an average of 2%, 6% is inside the limits for
  50 parts and a signal for 500.
- A point below the lower limit is a signal too: better than usual, or a
  test that stopped rejecting. Ask which.
- When nearly every point is outside (thousands of parts per sample), use
  Laney's chart: `zi = (p - pbar) / sqrt(pbar * (1 - pbar) / n)`, `sigma_z`
  their mean moving range over the baseline divided by 1.128, limits
  widened by `sigma_z`. Defects per unit (u chart): `ubar` (all defects
  over all units) in place of `pbar * (1 - pbar)`.

## Capability and performance indices

Continue from `rules` of the individuals chart. The specification limits
are the user's; left NULL, the query answers that they are missing.
`bounded` is the user's answer whether the value cannot go below zero
(roundness, runout, flatness, a one-sided form tolerance); NULL until asked.

```sql
spec AS (SELECT NULL::numeric AS lsl, NULL::numeric AS usl,   -- the user's limits and their source; one NULL: one-sided
                NULL::boolean AS bounded),
checked AS (
  SELECT l.status AS limits_status, l.warning, l.n, l.cl AS mean, l.sigma AS sigma_within,
         (SELECT stddev_samp(x) FROM pts WHERE baseline) AS sigma_overall,
         (SELECT avg(power(x - l.cl, 3)) / NULLIF(power(avg(power(x - l.cl, 2)), 1.5), 0)
            FROM pts WHERE baseline) AS skewness,
         (SELECT count(*) FROM pts WHERE baseline AND (x < s.lsl OR x > s.usl)) AS outside_spec,
         (SELECT max(abs(z)) FROM rules WHERE baseline) AS max_z,
         (SELECT count(*) FROM rules WHERE baseline
            AND (rule1 OR rule2 OR rule3 OR rule4 OR trend OR range_signal)) AS baseline_signals,
         (SELECT count(*) FROM rules WHERE baseline AND (rule1 OR range_signal OR rule4 OR trend)) AS gate_points,
         ceil(0.025 * l.n + 3 * sqrt(0.025 * l.n)) AS chance_cap,
         (SELECT abs(avg(x) FILTER (WHERE 2 * k > cnt) - avg(x) FILTER (WHERE 2 * k <= cnt))
                 / NULLIF(l.sigma * sqrt(1.0 / count(*) FILTER (WHERE 2 * k <= cnt)
                                         + 1.0 / count(*) FILTER (WHERE 2 * k > cnt)), 0)
            FROM (SELECT x, row_number() OVER (ORDER BY tsp, part_id) AS k, count(*) OVER () AS cnt
                  FROM pts WHERE baseline) h) AS halves_z,                 -- second half against the first
         (SELECT min(x) FROM pts WHERE baseline) AS min_x,
         s.lsl, s.usl, s.bounded
  FROM limits l, spec s
),
ok AS (
  SELECT *, CASE WHEN limits_status <> 'ok' THEN limits_status
                 WHEN n < 100 THEN 'too few values for an index: ' || n || ', at least 100'
                 WHEN lsl IS NULL AND usl IS NULL THEN 'no specification limits: ask for them'
                 WHEN lsl >= usl THEN 'the lower specification limit is not below the upper'
                 WHEN bounded IS NULL AND min_x >= 0
                      AND (lsl IS NULL OR usl IS NULL OR (lsl >= 0 AND mean < 4.5 * sigma_overall))
                   THEN 'ask whether the value is bounded at zero (roundness, runout, flatness); no index until then'
                 WHEN bounded THEN 'bounded characteristic: no index from a normal model; '
                                   || outside_spec || ' of ' || n || ' values beyond the limit'
                 WHEN warning IS NOT NULL THEN warning || '; no index'
                 WHEN max_z > 4.5
                   THEN 'a value ' || round(max_z, 1) || ' sigma from the centre: find its cause; no index'
                 WHEN halves_z > 3
                   THEN 'the mean moved between the halves of the baseline (' || round(halves_z, 1) || ' sigma): no index'
                 WHEN sigma_overall / sigma_within NOT BETWEEN 0.75 AND 1.33
                   THEN 'sigma overall is ' || round(sigma_overall / sigma_within, 2)
                        || ' times sigma within: drift, shifts or mixed streams; no index'
                 WHEN gate_points > chance_cap
                   THEN 'not stable: ' || gate_points || ' signals, more than chance gives (' || chance_cap || '); no index'
                 WHEN abs(skewness) > 2.5 * sqrt(6.0 / n)
                   THEN 'not normal (skewness ' || round(skewness, 2) || '): no index by the normal formulas'
                 ELSE 'ok' END AS status
  FROM checked
),
idx AS (        -- Cp/Cpk with sigma within (effective degrees of freedom 0.62 (n - 1)), Pp/Ppk with sigma overall
  SELECT w.kind, w.sigma, w.nu,
         (o.usl - o.lsl) / (6 * w.sigma) AS two_sided,
         (o.usl - o.mean) / (3 * w.sigma) AS upper, (o.mean - o.lsl) / (3 * w.sigma) AS lower
  FROM ok o CROSS JOIN LATERAL (VALUES ('Cp, Cpk', o.sigma_within, 0.62 * (o.n - 1)),
                                       ('Pp, Ppk', o.sigma_overall, o.n - 1.0)) AS w(kind, sigma, nu)
  WHERE o.status = 'ok'
)
SELECT o.status, o.n, o.baseline_signals, round(o.halves_z, 2) AS halves_z, round(o.mean, 4) AS mean,
       round(o.skewness, 2) AS skewness,
       o.outside_spec, o.lsl, o.usl, round(o.sigma_overall / NULLIF(o.sigma_within, 0), 2) AS overall_to_within,
       i.kind, round(i.sigma, 4) AS sigma, round(i.two_sided, 3) AS cp_or_pp,
       round(least(i.upper, i.lower), 3) AS cpk_or_ppk,            -- one-sided: the one side there is
       round(i.upper, 3) AS upper_index, round(i.lower, 3) AS lower_index,
       round(least(i.upper, i.lower) - 1.96 * sqrt(1.0 / (9 * o.n) + power(least(i.upper, i.lower), 2) / (2 * i.nu)), 3) AS k_low_95,
       round(least(i.upper, i.lower) + 1.96 * sqrt(1.0 / (9 * o.n) + power(least(i.upper, i.lower), 2) / (2 * i.nu)), 3) AS k_high_95,
       round(i.two_sided * sqrt(power(1 - 2.0 / (9 * i.nu) - 1.96 * sqrt(2.0 / (9 * i.nu)), 3)), 3) AS two_sided_low_95,
       round(i.two_sided * sqrt(power(1 - 2.0 / (9 * i.nu) + 1.96 * sqrt(2.0 / (9 * i.nu)), 3)), 3) AS two_sided_high_95
FROM ok o LEFT JOIN idx i ON true
ORDER BY i.kind;
```

- One row per family when the status is `ok`, else one row with the reason
  and no index; say it in plain words.
- `ok` means no sign of instability beyond chance in n values, not proof
  of stability. Simulated on 100 values: the gate refuses 2 to 3% of stable
  normal baselines; it refuses 97% of baselines with a 1 sigma shift half
  way and 98% with a 2 sigma drift, but passes 67% with a 0.5 sigma shift
  (reported Cpk 1.23, true 1.17 after it), 65% with a 1 sigma drift (1.15
  against 1.00 at the end), 51% with lag-1 autocorrelation 0.3 (Cpk 1.51
  against 1.33; Ppk 1.34 is right) and 99% of two streams mixed in random
  order. So report Ppk beside Cpk and the period, and ask whether the
  baseline held a change.
- `baseline_signals` up to the cap are listed beside the index; several
  rule 4 or trend points in a row still point to a change. With a known
  cause, put the time range into `excluded` and run again.
- A characteristic bounded at zero passes the normal checks often (a
  Rayleigh-shaped roundness in 55% of 100 values, Cpk 1.23 where the true
  Cpu is 1.00). With `bounded` true the query gives no index and the count
  beyond the limit; with 0 of n beyond, the share is below 3/n with 95%
  confidence (3% for 100 values). With `bounded` NULL it asks, unless a
  baseline value is below zero (then not bounded at zero) or, with two
  limits, the lower one is below zero or the mean lies 4.5 sigma overall
  or more above zero (then the bound is outside the process's spread and
  does not matter).
- Intervals are 95%: Bissell's for Cpk and Ppk, chi-square for Cp and Pp
  (Wilson-Hilferty quantile); with `nu` as above they covered 94 to 95% in
  simulation (with n - 1 for Cp/Cpk only 88%).
- `outside_spec` counts baseline values outside the specification: what
  was made, beside the prediction.
- A positive, right-skewed value: first count the values at or below
  zero (below). With any, the logarithm does not fit (a reading of 0 is
  the bound itself): treat it as bounded. With none, replace
  `m.diameter::numeric` by `ln(m.diameter)::numeric` in `pts`, add
  `AND m.diameter > 0` to its `WHERE`, set `bounded` false and the limits
  to their logarithms; the indices then refer to the logarithm, say so.

```sql
SELECT count(*) FILTER (WHERE diameter <= 0) AS not_positive, count(*) AS n
FROM part_measurements
WHERE machine_id = 'P-3' AND diameter IS NOT NULL
  AND tsp >= timestamptz '2026-11-02 06:00 Europe/Berlin'
  AND tsp <  timestamptz '2026-11-09 06:00 Europe/Berlin';
```
