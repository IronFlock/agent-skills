# Technical availability of a machine (VDI 3423)

How available a machine was, counting only what the machine itself is
responsible for: the question of a builder who watches its machines at
customers' plants. How well a plant runs is OEE (`oee.md`); the SQL is in
`technical-availability-sql.md`.

## The guideline and this text

VDI 3423, "Technical availability of machines and production lines; terms,
definitions, determination of time periods and calculation" (Verfügbarkeit
von Maschinen und Anlagen), defines time categories and availability
figures for single machines and lines. This text was written from public
descriptions of the guideline, not from the document: a figure computed
with it follows the guideline's definition as publicly described. For a
clause, the guideline's own examples or a term not described here, say that
the document or the contract decides; do not answer from memory.

**A contract decides its own figure.** An availability agreed in a contract
is measured with the contract's definitions, category list, observation
period and recording procedure. Ask for them,
use them, name every point where the computation departs from them, and say
that the binding figure is the one the contract's procedure yields.

## Time categories

| Category | Meaning | German |
| --- | --- | --- |
| Occupied time T_B | The time the user plans to use the machine, from the user's plan; planned breaks, days off and unplanned shifts lie outside it | Belegungszeit |
| Utilisation time T_N | Occupied time in which the machine was used | Nutzungszeit |
| Technical downtime T_T | Stops the machine causes: a material defect of a component, a design or execution fault, faulty documentation | technische Ausfallzeit |
| Organisational downtime T_O | Stops the user's side causes: missing material, tools, staff or energy, operating or programming errors, a fault reported late, waiting for spare parts the user agreed to keep | organisatorische Ausfallzeit |
| Maintenance time T_W | Planned preventive maintenance in occupied time | Wartungszeit |
| Test time T_C | Time for tests and trial runs; where it belongs is open (below) | Testzeit |
| Consequential downtime | In a line: this machine stands because another one failed (starved, blocked); recorded at this machine and reported apart; how it counts is for the contract | Folgeausfallzeit |

## The figure

```text
Technical availability V_T = 1 - T_T / T_B
Degree of utilisation N_G = T_N / T_B        (all causes)
```

V_T (technische Verfügbarkeit) is the share of occupied time in which the
machine was not down through its own fault. Most public descriptions give
it this way: organisational downtime and maintenance lower N_G
(Gesamtnutzungsgrad) but not V_T. They differ on these points; take the
contract's choice, or ask and state it, and never present one as the
guideline's rule:

- **Planned maintenance**: left in T_B; or taken out of the base,
  1 - T_T / (T_B - T_W), as in some supplier agreements; or counted against
  technical availability, as in some reliability texts.
- **Test time**: part of utilisation time, or a category of its own.
- **No orders**: organisational downtime, or time not occupied (then T_B
  is smaller and V_T lower).
- **Start and end of a technical stop**: from the fault, or from the report
  to the supplier, perhaps only in the supplier's working hours; until the
  fault is cleared, or until the machine is handed back.
- **MTBF / (MTBF + MTTR)** is called technical availability in some texts.
  Its base is operating time plus repair time, without organisational
  downtime and maintenance, so it is a different figure; never mix the two.

## Sorting stops into categories

- Each stop gets its category from its reason code, alarm number or alarm
  class, through a mapping the builder and the user agree on, best the one
  in the contract. Never from a code's name or a guess: a code without a
  mapping is unknown.
- An alarm that does not stop the machine (a warning, a message) is no
  stop: map it so and leave it out, or it hides real faults under it. Where
  the machine writes states, the states decide when it stood and their
  values must carry the reason (below).
- Doubtful cases (overlapping stops of different categories, a fault after
  wrong operation, waiting for the supplier's technician,
  a fault after the user's own repair) are decided by the contract or by
  both sides. List them; never decide them for one side.
- Overlapping stops: each minute counts once. By default the stop that
  began first owns the time until it ends, then the next; counting
  technical first is the other convention. Say which, and report the
  technical minutes the rule gave to another category.
- A stop crossing the period or occupied time counts only inside both, and
  as one stop in the period of its first occupied minute: list the windows
  back to the earliest stop, also for monthly rows. A stop still open
  counts until now; flag every open one with its start (an alarm open for
  weeks is usually a lost end).
- OEE's micro-stop threshold does not apply: every stop counts unless the
  contract sets a minimum length.

## Missing reasons and missing data

When no stop has a reason, the split cannot be made: V_T is not
computable. Never count all stops as technical, and never none. Report
occupied time, stop hours and N_G, and ask for the reasons or a mapping.
When some stops lack one, report V_T as a range: low with them counted as
technical, high with them not, beside their number and hours. A generic
stop state with the reasons as alarm codes elsewhere cannot be joined here:
explain that to the user and offer the alarm rows as stops, or a state per
reason.

Time without data leaves the base and is reported. A fault that cuts the
logger's power would leave the base too instead of lowering V_T: list every
outage in occupied time and ask what happened; in a contract figure never
drop one silently.

## Difference to OEE availability

| | Technical availability | OEE availability |
| --- | --- | --- |
| Base | Occupied time | Planned production time (planned maintenance taken out) |
| Lowered by | Technical downtime only | Every unplanned stop |

Public descriptions treat OEE as a separate system with another base.
Example: shift 480 min with a 30 min break, so occupied time 450 min;
planned maintenance 30, technical stops 20, no material 60, so utilisation
time 340. V_T = 1 - 20/450 = 95.6% (95.2% with maintenance out of the
base). OEE availability = 340/420 = 81.0%. N_G = 340/450 = 75.6%. Name
which figure you report.

## Observation period

- Use the contract's period: a month, a year, the warranty.
- Short periods mislead: one stop moves V_T by its length / T_B; 4 hours
  in 80 occupied hours cost 5 points, in 4,000 hours 0.1.
- Say when there are few technical stops or little occupied time; ask
  whether a run-in phase is excluded.
- Each customer's occupied time, in its own time zone, sets its period.

## Machines of one type at several customers

- Compute per machine, then pool by sums on the same base: 1 - sum T_T /
  sum T_B. Never average percentages: a machine with few hours would weigh
  as much as one with many.
- Pool only where the mapping is the same (one firmware's alarm numbers,
  not each customer's own codes).
- Leave out and name machines without data or reasons.
- Show which machines pull the figure down; rank technical stops by minutes
  and by count (`downtime-losses.md`). A pooled figure is no contract's.

## What to report

The period and the customer's time zone; occupied time and its source;
hours per category, time without data and the outages; stops per category,
how many had no reason, and open stops; V_T or its range, to two decimals
beside an agreed value; the choices made (maintenance, test time, overlaps,
start and end of a stop); N_G beside it. Say that the figure follows VDI
3423 as publicly described, and that a contractual figure is measured by
the contract.
