# Failures, repair times and reliability

Failure and repair figures from machine data: the terms, MTBF, MTTR,
failure rate, the availability built from them, planned maintenance, and
what the data cannot show. The SQL is in `maintenance-reliability-sql.md`.
Ranking stops is `downtime-losses.md`; why a machine failed, or why its
failure rate changed, is `root-cause-checks.md`.

## Standards

- **EN 13306, Maintenance - Maintenance terminology** (DIN EN 13306,
  Instandhaltung - Begriffe der Instandhaltung): the vocabulary of
  maintenance: item, failure, fault, the kinds of maintenance (preventive,
  condition-based, predictive, corrective, deferred) and the times around a
  maintenance action. Applies where a plant, contract or maintenance system
  uses them.
- **EN 15341, Maintenance - Maintenance Key Performance Indicators**: a set
  of indicators for the maintenance function (economic, technical,
  organisational) and how to choose them. Applies when a maintenance
  department reports or benchmarks itself.
- **IEC 60050-192, International Electrotechnical Vocabulary - Part 192:
  Dependability**: reliability, availability and maintainability terms and
  measures such as mean operating time between failures and mean time to
  restoration. Free to read online (Electropedia).

The figures here follow these definitions as publicly described; never say a
figure conforms to a standard. When a question needs a standard's exact
wording, say so and point to the document.

## Terms kept apart

- **Failure** (Ausfall): the event: the machine loses its ability to work as
  required. **Fault** (on the display often Störung): the state that
  follows, until it is restored. Planned maintenance and a lack of external
  resources (material, operator, utilities) are no fault.
- **Stop** (Stillstand): any time the machine does not produce.
- **Alarm** (Alarm, Meldung): a message of the control at one moment, before,
  during or without a stop. Several alarms in one stop are one failure; a
  fault alarm without a stop, or during planned maintenance, is no failure.
- **Downtime** (Stillstandszeit) in plant use means any stop. In IEC usage,
  down time is time in a down state: the machine's own fault or its
  maintenance, not waiting for material or staff. Say which one.
- **Time to restoration**: from the failure (or its
  detection) until the fault is cleared, waiting for staff and parts
  included. **Active repair time** (Reparaturzeit): only the hands-on work.
- **MTTR** means mean time to restoration in IEC usage; many plants mean
  mean time to repair. Machine data gives the time from the failure until
  its fault ends: the time to restoration as the machine saw it, never the
  repair time. Say which a figure is.
- **Operating time between failures** counts run time only, from the
  restoration to the next failure. Calendar time adds nights, weekends,
  planned stops and waiting: a one-shift, five-day machine looks about four
  times as reliable by the calendar. Use operating time and say so; some
  vendors count from failure to failure, repair included: ask.
- **MTBF** is for repairable items (a machine); **MTTF** (mean time to
  failure) is commonly used for items replaced, not repaired (a bearing, a
  fuse): their life. A machine's **mean time to first failure** (after
  delivery or an overhaul) differs from its MTBF when early failures or wear
  dominate.

## Which stops are failures

- Only the machine's own unplanned stops. Not planned maintenance, breaks,
  changeovers, waiting (material, operator, the line around it, utilities,
  orders), nor a fault stop shorter than the micro-stop threshold (`oee.md`):
  count those apart.
- The split needs a class per state, reason or alarm code, from the column
  descriptions or the user, and for alarms how long before a stop its alarm
  may come. Ask once. One stop with a failure is one failure, however many
  rows, reasons or alarms it holds; each alarm belongs to one stop.
- Report the share of stops without a class first (`downtime-losses.md`).
- Without classes, never call a figure MTBF or MTTR. Report "mean run time
  between unplanned stops" and "mean stop length", named so, and say that a
  reason per stop would split them.

## The figures

Per machine and period: operating time T (run time in the period), N
failures that began in it, the restoration time of each closed failure.

- **Failure rate** (Ausfallrate) = N / T, per 1000 operating hours.
- **MTBF** (mittlere Betriebsdauer zwischen Ausfällen) = T / N: how long it
  runs before it fails. T includes the run after the last failure, so T / N
  differs from the mean of the listed intervals; give both.
- **MTTR** = sum of restoration times / closed failures: how long a failure
  keeps it out.
- **Mean active repair time**: only from repair states or a maintenance
  system; say for how many failures it was recorded.
- **Availability from them** = MTBF / (MTBF + MTTR). It ignores planned
  stops, waiting and idle time, so it is neither OEE availability (`oee.md`)
  nor a builder's technical availability; name which one.
- **Share of planned maintenance** = planned maintenance minutes / (planned
  maintenance plus fault and repair minutes), where the data shows planned
  maintenance as a state or reason.

When they mean something:

- Under about five failures a mean says little; with one, nothing. Always
  give N and T. Up to ten failures also give the 95% lower confidence limit,
  assuming a steady failure rate (factors in `maintenance-reliability-sql.md`):
  with no failure, MTBF is at least T / 3. Zero failures is "no failure in T
  operating hours", never an MTBF. That assumption is doubtful after an
  overhaul and for pooled machines.
- Restoration times are skewed: a few long ones carry the mean. Give the
  median and longest beside MTTR; from ten failures, the 90th percentile.
- A failure counts in the period it began. One whose end is not in the data
  stays out of MTTR: "open since" when the period ends now, otherwise "at
  least" its length so far.
- Restoration is a range when a gap lies in it or unclassified stop time
  precedes it. A gap up to a stated length (30 minutes unless the user
  gives one) keeps a failure one (a stop list shows two stops: say both).
  Across a longer gap, count, MTBF, failure rate and MTTR have two ends:
  report both. A time between failures across a gap is incomplete.

## What the data cannot show

Whether a stop was maintenance at all unless a state or reason says so,
which component failed, what was repaired, by whom, with which spare part,
how long the hands-on work took, how long parts were awaited, what it cost,
or whether a planned task was done on time: that is a maintenance system's
data (CMMS, work orders, Instandhaltungsaufträge). Name what to add: a class
per reason or alarm code; a repair state or a technician's start and end of
work at the machine; work orders with machine, failure time, component,
action, parts, hours and cost, linked to the stops by machine and time.
Never guess them.

## Indicators that need other data

EN 15341 also has indicators machine data cannot give; name them and ask
for their source: maintenance cost against asset replacement value, output
or turnover; preventive against corrective work in staff hours or cost;
staff hours, overtime, training, own against contracted work; spare parts
stock and turnover; work orders done on time, backlog; injuries and
environmental incidents in maintenance work.

## Combining machines and periods

Sum, then divide: MTBF = sum of T / sum of N, MTTR = sum of restoration
times / sum of closed failures, failure rate = sum of N / sum of T. Never
average the means: a machine with 100 hours and 1 failure and one with 100
hours and 4 give 40 hours pooled, not 62.5. A machine without failures adds
its T and no failure. Pool only machines of one type and use, and name them.
A live figure is kept as these sums per machine and period, never as ratios.
