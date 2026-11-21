<!-- Adapted from the claude-for-manufacturing plugin, version 1.0.0, by Anthropic, under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten for machine data in SQL tables. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-production-figures (IronFlock/agent-skills), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# OEE and its three parts

This file defines OEE (overall equipment effectiveness) and its three parts,
availability, performance and quality, and TEEP: the inputs each needs, what
each is not, how figures are combined across machines and periods, and what
to do when an input is missing. It holds for any machine or line whose data
are time-stamped rows in tables. How durations and counts are derived from
such rows is in `machine-data-sql.md`; stop and loss rankings are in
`downtime-losses.md`.

## Inputs

| Input | Meaning | German |
| --- | --- | --- |
| Planned production time | The time the machine was meant to produce in the period: shift time minus planned stops (breaks, planned maintenance, and only if the plant says so planned changeovers or time without orders). A definition of the plant, not a measurement. | Planbelegungszeit, geplante Produktionszeit |
| Run time | Planned production time minus the stops in it. | Hauptnutzungszeit, Laufzeit; "Betriebszeit" often means operating or planned time, so ask |
| Ideal cycle time | The fastest time per part the machine is designed or proven to reach, per product (or its inverse, the ideal rate). | ideale or theoretische Zykluszeit; a "Soll" value is often the planned or standard one: ask |
| Total count | Every part made in the period, good or not. | Gesamtmenge |
| Good count | Parts right the first time: neither scrap nor rework. | Gutmenge, Gutteile |

## Formulas

```text
Known time   = planned production time with usable state data = run time + stop time
Availability = run time / known time
Performance  = ideal cycle time x total count / run time
               (several products: sum of ideal cycle time x count, per product)
Quality      = good count / total count
               (several products: sum of ideal cycle time x good / sum of ideal cycle time x count)
OEE          = Availability x Performance x Quality
             = ideal cycle time x good count / known time (exactly)
TEEP         = ideal cycle time x good count / calendar time with usable state data
             = OEE x known time / that calendar time
```

Calendar time is all the time in the period, 24 hours a day. OEE is the
default; report TEEP only when asked for the use of all available time, and
name which one a figure is.

Worked example: shift 480 min, break 30 min, planned 450 min, stops 45 min,
run 405 min, ideal cycle time 1.0 min, total 360, good 342. Availability
405/450 = 90%, performance 360/405 = 88.9%, quality 342/360 = 95%,
OEE 76.0% = 342/450.

## What they are not

- **Availability is not uptime.** The edge device being online, the app
  sending data or the machine being powered on is not run time. A machine
  that is powered and waits for material, an operator or a part is stopped.
- **A planned stop is not downtime.** A break or planned maintenance leaves
  planned production time; it is no availability loss. Run time, stops and
  parts all count inside the planned windows only; production during a
  planned stop is outside OEE and reported apart. Changeovers are an
  availability loss unless the plant counts planned changeovers as planned
  stops; state which.
- **A micro-stop is a performance loss.** Stops shorter than a threshold the
  plant sets (often one to five minutes) are usually counted as run time, so
  they lower performance, not availability. OEE does not change with the
  threshold, only the split between availability and performance; state it.
- **Running slower than ideal is a performance loss**, never availability.
- **Rework is not good.** A reworked part was not right the first time. If
  the data holds no rework, say that quality is good / (good + scrap) and
  that rework could not be taken into account.
- **The ideal cycle time is not the planned, average or standard time.** If
  the plant uses a standard time instead, performance can exceed 100%; say
  so. It is also not takt time (available time divided by customer demand);
  in German both are called Taktzeit, so ask which one is meant.

## Show the parts apart

Always state availability, performance and quality next to OEE, with the
inputs, the period and the grain (which machine or line). The same 62% OEE
caused by availability is a maintenance question, caused by quality a
process question: the composite alone does not tell anyone what to do. On a
board the three parts are separate figures beside OEE.

## Grain and combining

- Compute per machine, or per line measured at its output, and per period;
  name both.
- To combine machines, products or periods, sum the inputs, then divide:
  availability = sum of run time / sum of known time, performance = sum of
  (ideal cycle time x total) / sum of run time, quality = sum of (ideal
  cycle time x good) / sum of (ideal cycle time x total), OEE = their
  product = sum of (ideal cycle time x good) / sum of known time. Quality
  weights each part by its ideal cycle time; good / total is the quality of
  one product and may be shown beside it. Machines at 76% (the example
  above) and 56% (240 planned minutes, run 200, ideal 0.4 min, 400 parts,
  336 good) pool to 69.0%: not their average 66%, and not 67.2% from good /
  total.
- Never average percentages, and never pool a sum that lacks an input of one
  machine: the pooled part is then not computable.
- A machine with no data in the period has no OEE. It is named as "no data"
  and left out of every figure and every sum, never counted as 0%.

## Absent is not zero

- A figure whose input the data does not hold is not computed. No ideal
  cycle time: no performance and no OEE, and quality only as good / total
  by count, said so. No planned production time: no
  availability (shares of calendar time can be shown, named as such). No
  split into good and scrap: no quality and no OEE. Say which input is
  missing and what would provide it, and report the parts that can be
  computed.
- Never put 100% or any default in place of a missing part. Availability
  78% x performance "1.0" x quality 96% reads as a fair day that nobody
  measured.
- An input the user gives (an ideal cycle time, a shift plan) is an
  assumption: name it next to every figure that uses it. A stand-in taken
  from the data, such as the best rate shown over a stated period, is used
  only when the user agrees, and named as that.
- Time without data (logger offline, a gap in the rows) or with an unknown
  state is neither run time nor stop time. Every part and OEE are computed
  over the planned time with usable state data; report the time left out
  beside them, and when it is a large share, say the figures are not
  representative. Parts counted in that time are left out and reported apart.
- No count rows: when the state rows show no run time in the period, the
  count is 0, a known zero; with run time but no count rows, the counts are
  missing (not computable); with no state data the machine is left out.

## Checks before reporting

- Each part between 0 and 100%. A value above 100% is a finding, never
  capped: performance over 100% means the ideal cycle time is too slow or
  parts are counted twice. Run time outside the planned windows (unscheduled
  overtime, a wrong plan) is a finding too.
- Run time + stop time + unknown state + time without data = planned
  production time, all clipped to the planned windows. Parts counted while the machine did not
  run are a finding.
- Good count <= total count; total = good + scrap (+ rework) where the data
  holds them separately.
- Discrete production commonly runs at 60 to 70% OEE; 85% is often called
  world class. A figure far above that is checked before it is reported.

## German terms

OEE is used in German too; also Gesamtanlageneffektivität (GAE).
Availability Verfügbarkeit, performance Leistung (Leistungsgrad), quality
Qualität (Qualitätsrate), stop Stillstand, micro-stop Kurzstillstand,
scrap Ausschuss, rework Nacharbeit, changeover Rüsten (Rüstzeit), shift
Schicht.
