# Semiconductor equipment: SEMI E10 states and E79 figures

Equipment states of semiconductor tools and the figures built on them,
written from public descriptions (papers, vendors' guides, SEMI's
catalogue), not from the standards' text: a figure follows the definition
as publicly described, never "according to" the standard. Say so when a
question goes beyond this text (an edition's sub-states, exact limits):
the fab's copy of the current edition decides. OEE and losses in general:
`oee.md`, `downtime-losses.md`; SQL: `semiconductor-equipment-sql.md`.

## The standards

- **SEMI E10**, Specification for Definition and Measurement of Equipment
  Reliability, Availability, and Maintainability (RAM) and Utilization: six
  basic equipment states, the time groups built from them, and the figures.
  Rewritten in 2012 and 2014 and revised since: sub-states and details of
  figures changed, the six basic states did not. Since 2012 it also has rules for intended process sets
  and multi-path cluster tools, which this text does not hold.
- **SEMI E79**, Specification for Definition and Measurement of Equipment
  Productivity: overall equipment efficiency (OEE) and its parts, on E10
  time.
- **SEMI E116**, Specification for Equipment Performance Tracking: busy,
  idle and blocked time of equipment and modules, and why; not E10 states.
- **SEMI E58** (ARAMS, automated reporting of E10 states) and **SEMI E124**
  (Overall Factory Efficiency, the factory level) are inactive at SEMI.

## The six states

| State | The tool | Examples |
| --- | --- | --- |
| Productive (PRD) | does its intended function on production units | regular lots, rework |
| Standby (SBY) | could run, but does not | no operator, no wafers, waiting for a result |
| Engineering (ENG) | could run, used for experiments | process or equipment development |
| Scheduled downtime (SDT) | cannot run, for a planned reason | preventive maintenance, consumables, setup |
| Unscheduled downtime (UDT) | cannot run, for an unplanned reason | failure, repair, waiting for parts, facility outage |
| Non-scheduled (NST) | is not planned for use | unworked shifts, holidays, shutdown, installation, upgrade |

Every hour of the period is in exactly one. The groups:

```text
total time         = all calendar time of the period
operations time    = total time - non-scheduled
equipment uptime   = productive + standby + engineering
equipment downtime = scheduled + unscheduled downtime
manufacturing time = productive + standby
```

Where sources and fabs differ, ask and say which rule a figure used:

- A vendor guide counts engineering on a tool that production could not
  have used anyway as downtime.
- Some fabs book idle days without work as non-scheduled, which raises
  every figure over operations time.
- Sub-state lists (where qualification runs or setups belong) differ
  between editions and fabs: take them from the fab.

## Availability and utilization

| Figure | Divides | by |
| --- | --- | --- |
| Total uptime | equipment uptime | total time |
| Operational uptime | equipment uptime | operations time |
| Total utilization | productive time | total time |
| Operational utilization | productive time | operations time |
| Productive share of manufacturing time | productive time | productive + standby |

The denominator decides the number: one tool's day of 14 productive, 1
standby, 1 engineering, 6 down and 2 non-scheduled hours is 58.3% total
utilization, 63.6% operational utilization, 66.7% total uptime and 72.7%
operational uptime. Always name the figure with its denominator. The last
row is what capacity planners often call "utilization"; ask which is meant.
Equipment-dependent and supplier-dependent uptime leave downtime the tool
(or its supplier) did not cause out of the denominator; ask the fab which
before computing them.

## Reliability and maintainability

- **Mean productive time between failures** = productive time / failures,
  not calendar time: a tool idle half the month must not look twice as
  reliable. Some fabs divide uptime instead: name which.
- **Mean cycles between failures** = cycles / failures. A cycle is what the
  fab says: a run (always on a batch tool), a wafer, a lot. Say which, and
  from which states the cycles came.
- **Restore and repair**: the mean length of a failure, waiting for parts
  and technicians included, is the mean time to restore; the mean of the
  repair work alone is the mean time to repair. Sources and fabs use
  "MTTR" for both: ask, and name the one shown. **Mean time off-line** =
  downtime / downtime events.
- Which unscheduled downtime is a failure of the tool is the fab's rule;
  a facility outage or bad incoming material is not. No failure: "no
  failure in N productive hours", never a number; no productive time: not
  computable.

Failure and repair figures beyond E10 are in
`maintenance-reliability.md`.

## Compared with OEE in `oee.md`

E10 uptime asks whether the tool *could* run; the core's availability
whether it ran in planned time: a tool waiting for wafers is up in E10 and
stopped in OEE. By default productive is running; standby and unscheduled
downtime are stops; engineering and scheduled downtime are planned stops,
except setups, which are stops as `oee.md` says of changeovers unless the
fab counts them as planned; non-scheduled is outside the plan. If the fab
books idle days as non-scheduled, ask for the shift plan instead.

## E79: equipment productivity

E79's OEE (overall equipment *efficiency*) multiplies four parts:

```text
availability efficiency = equipment uptime / total time
operational efficiency  = productive time / equipment uptime
rate efficiency         = theoretical production time of the units processed / productive time
quality efficiency      = theoretical production time of the good units / that of all units
OEE                     = their product = theoretical time of the good units / total time
```

Operational x rate efficiency is called performance efficiency. The
theoretical production time per unit, tool and recipe plays the part of the
ideal cycle time; it comes from the fab. How it differs from the core's OEE:

- Over total time it is closer to the core's TEEP than to its OEE. Some
  public descriptions divide availability efficiency by operations time
  instead; show which, never both under one name.
- Standby and engineering lower operational efficiency, not availability.
- Quality is weighted by theoretical time, as pooled quality in `oee.md`.
  What a good unit is (a wafer neither scrapped nor reworked, or good
  dies) differs between sources: ask the fab.

## What the data must hold

- A state per tool with its time, as E10 names or the fab's codes. Cluster
  tools: E10 has rules for tools and their chambers that this text does
  not hold; never add chamber hours as tool hours.
- For failures: the sub-state or reason that tells a tool failure, and
  repair from waiting, apart; without it every unscheduled downtime is a
  failure and restore is all that can be shown, said so.
- For cycles and E79: runs per tool with recipe, wafers and good wafers,
  and the theoretical time per tool and recipe.

Without states, no E10 figure. Without theoretical times, no rate
efficiency and no E79 OEE. Without runs, no cycles between failures. Name
the missing input; never a default. German terms of the core: `oee.md`.
