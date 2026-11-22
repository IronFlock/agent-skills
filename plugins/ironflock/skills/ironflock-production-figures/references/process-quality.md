# Process quality: control charts and capability

This file covers whether a characteristic measured per part or cycle (a
dimension, a torque) is stable, where it changed, and whether it is
capable of its specification. It goes beyond the
individuals check of `root-cause-checks.md`: run rules 2 and 3, the moving
range chart, limits held from a baseline, and capability indices. Charts,
constants and SQL: `process-quality-sql.md`.

## Standards

The methods are textbook statistics, written from textbooks and public
descriptions of the standards, not from the documents. Say that a chart or
index follows the usual definitions, never that it conforms to a
standard; for what a part requires in detail, say this file does not hold
it.

- **ISO 7870, Control charts.** Part 1 General guidelines; Part 2
  Shewhart control charts (the charts here); Part 4 Cumulative sum charts
  and Part 6 EWMA control charts for the process mean (small shifts); Part
  8 Charting techniques for short runs and small mixed batches; Part 9
  Control charts for stationary processes (autocorrelated values).
- **ISO 22514, Statistical methods in process management, Capability and
  performance.** Part 1 General principles and concepts; Part 2 Process
  capability and performance of time-dependent process models (not normal
  or moving over time); Part 3 Machine performance studies for measured
  data on discrete parts; Part 4 Process capability estimates and
  performance measures; Part 7 Capability of measurement processes.

## Stable first, then capable

- Chart a baseline first. A capability index on an unstable process
  describes a mixture and predicts nothing. Asked for one, show the
  signals with their times and offer what holds: the share outside the
  specification in that period, and Pp/Ppk labelled as describing that
  period only.
- A stable process signals by chance, so the index query accepts signals
  up to what chance gives and lists them. Several rule 4 or trend points in
  a row still point to a change. With a known cause, leave those points
  out with the user's agreement and compute again once.

## Which chart

One value per part: individuals and moving range (I-MR). Subgroups:
means with ranges up to 10 parts, with standard deviations above. Share
of defective parts per sample: p chart; defects per unit: u chart; with
thousands of parts per sample nearly every p point is outside, use
Laney's p'. A subgroup (Stichprobe) is a few consecutive parts under the
same conditions; never mix machines, cavities or spindles, never spread
one over a shift: the limits come out so wide that nothing signals.

## Limits

- Control limits come from the process, never from the specification;
  specification limits appear only labelled as such. A process can be
  inside its specification and out of control.
- From a baseline the user calls normal: at least 25 values or 20
  subgroups; with fewer, no limits.
- Hold them: a fixed baseline, new points judged against it. Compute again
  only after a deliberate change, with its date. Limits over a moving
  window take a drift in and never show it.

## Signals

Rules 1 to 4 of the Western Electric handbook, the trend rule of the
Nelson rules, and the moving range above its limit; a stable process gives
a false alarm about every 52 points with all of them (rule 1 alone: 370).
More rules find small shifts sooner and raise more false alarms; use the
plant's own set when the user names one.

## Capability and performance

- sigma within: MR-bar / 1.128, R-bar / d2 or s-bar / c4; sigma overall:
  the standard deviation of all values. Cp = (USL - LSL) / 6 sigma within;
  Cpk = min(USL - mean, mean - LSL) / 3 sigma within; Pp, Ppk the same with
  sigma overall.
- One-sided specification: only Cpu (or Cpl, Ppu, Ppl), no Cp.
- Assumed: stable, close to normal, independent, at least 100 values over
  a period with the usual variation (shifts, lots, tool changes). The SQL
  refuses an index on a sign of instability and says why; that reason is
  the answer. Accepted means no sign beyond chance in n values, not
  proof: a small shift or drift still passes. Say so, give Ppk beside Cpk,
  and ask whether the period held a change.
- Bounded at zero (roundness, runout, flatness): a normal model overstates
  the capability. Ask whether the value is; never assume it. If so, the
  logarithm where no value is zero, else no index: the count beyond the
  limit; with 0 of n, the share is below 3/n (95%).
- Give the 95% interval: Ppk 1.33 from 30 values lies between 0.97 and
  1.69, from 100 between 1.13 and 1.53; Cpk's is wider.
- Cpk far above Ppk: the parts drift or shift between times; far below:
  they alternate. Neither is a capability.
- Not normal: the logarithm (the SQL does it), or the percentile method,
  not computed here: Cpu = (USL - median) / (99.865% point - median), Cpl =
  (median - LSL) / (median - 0.135% point), the points from a fitted
  distribution.
- Report an index with sample size, period, which sigma, the
  specification limits and their source, the interval and the share
  outside; without sample size and period, not at all. Whether 1.33 or
  1.67 is enough is the customer's or plant's rule: ask.
- Cm, Cmk (Maschinenfähigkeit): a short study on consecutive parts by
  the plant's procedure.

## What machine data lacks

- **Specification limits:** ask, with their source; never alarm limits,
  setpoints or the data range.
- **One value per part or cycle**, as the user defines it (peak, mean,
  final), never every sensor reading.
- **Autocorrelation:** above about 0.3 at lag 1 the limits are too
  narrow; with limits from 100 values, a stable process falls outside 4%
  of the time at 0.5, 38% at 0.9. Space the values further apart; if that
  does not help, the standard chart does not apply (Part 9, EWMA).
- **Alternation** (negative lag 1): two streams in one column, such as
  cavities or spindles, or over-adjustment. One chart per stream.
- **Tool wear:** a drift reset at each tool change is expected. Chart the
  deviation from the expected wear, or report Pp/Ppk over whole tool
  lives, labelled; Cpk overstates such a process.
- **Resolution:** with four or fewer reading steps under the range limit,
  the reading is too coarse for a chart.
- **Conditions:** one chart per machine, cavity or spindle, product and
  characteristic; warm-up after a stop left out, as in
  `root-cause-checks.md`.

## On a board

widget-linechart, all series from one transform with one row per part:
the values as a line with `data[].r` bound to a constant
(`r: $num:6`), since the marker size comes from `r` and is 0 without it;
centre and limits as series with `styling.borderDash: dashed` and
`styling.pointStyle: none`; signals as a `scatter` series on `signal_x`
(NULL except at a signal); specification limits labelled, in another
colour. Below, the range chart from `spread` and its limits, its signals
on `signal_spread`. Indices as widget-value tiles with sample size and
period in the label. The transform reads the last days and a fixed
baseline; its description names the baseline, the limits and the source
of the specification.
