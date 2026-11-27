# Further figures of ISO 22400

## Orientation

ISO 22400-2 (Automation systems and integration: key performance
indicators for manufacturing operations management, Part 2: Definitions and
descriptions; 2014, amended 2017, a new edition in preparation) defines 34
figures for machines and lines at the level of manufacturing operations,
each with its formula and inputs; part 1 holds the concepts and terms. VDMA
66412-1 (Manufacturing Execution Systems (MES) Kennzahlen) is the German
specification of similar figures. This file follows public descriptions of
both, not their texts: never say a figure conforms to them, and for an exact
wording or a clause say this file does not hold it. A plant's own
definition (in its MES, a contract) wins: compute it and name the difference.

Time model: planned busy time (Planbelegungszeit) is the planned operation
time minus planned stops; in it the machine is busy with an order (setup,
production, stops) or idle; actual production time (Hauptnutzungszeit) is
producing only. Planned values come from planning, not from the machine.
Every rule of `oee.md` holds here. SQL: `iso-22400-figures-sql.md`.

## The core figures in the standard's terms

In ISO 22400-2 the planned production time of `oee.md` is the planned busy
time, run time the actual production time, performance the effectiveness,
quality the quality ratio, OEE the OEE index; availability keeps its name;
TEEP is not in it. Different on purpose:

- micro-stops are run time (the standard counts only producing time);
- time without state data leaves the denominator;
- performance uses the ideal cycle time, not the planned time per part;
- pooled quality is weighted by ideal cycle time, so the parts multiply to
  OEE;
- `oee.md` lets a plant count planned changeovers as planned stops, while
  public descriptions keep setup inside planned busy time; then planned
  production time is the smaller one, and setup ratio and allocation
  efficiency need the setups back in: say so.

Sources differ on whether planned maintenance and time without orders are
planned stops.

## Setup ratio (Rüstgrad)

Setup time / (setup time + run time). Needs a setup state (or setup events),
mapped as a stop and classed as setup. Without one it is not computable;
never read long stops as setups.

## Technical efficiency

Run time / (run time + time stopped by faults of the machine); other stops
are left out. Every stop state needs a class; an unclassified one makes the
figure not computable. Micro-stops are run time here, while public
descriptions put minor stoppages into the standard's delay time. The
technical availability machine builders agree on: `technical-availability.md`.

## Allocation and utilisation efficiency

Allocation efficiency = busy time / known time (planned busy time with
usable state data); utilisation efficiency = run time in orders / busy
time. Their product is availability when all run time lies in orders;
report run time outside orders. Needs order intervals per machine (an order
or batch column, or start and end rows; an open order has no end); orders of
one machine must not overlap. A machine without order data, or whose last
order ended before the period, has neither ("no current order data"),
never 0%; never take planned time as busy time.

## First pass yield, scrap and rework

- First pass yield (FPY, used in German too) = good first passes / all
  first passes (one first pass per part). Needs a result per pass and a part id;
  the first pass is looked for over a lookback longer than rework takes.
  Public descriptions differ on the denominator: state it, and show the
  later passes beside it (good passes / all passes is higher).
- Scrap ratio (Ausschussquote) = passes scrapped / produced quantity; rework
  ratio = passes sent to rework / produced quantity: as publicly described.
  Produced quantity here: first passes and passes after rework; a part
  tested again after a good or scrap result is left out and counted apart.
- First-pass scrap and rework shares count over first passes; with FPY
  they add up to 100%. Final yield = parts finally good / first passes.
- Without part ids, give good / total as quality by count (`oee.md`). Rows
  without a part id or a result are counted apart. The yield over several
  steps is the product of their FPYs, never pooled. Never add pieces, kg
  and boxes. Results and counters count over the period; join them to the
  shift calendar to clip them to planned windows.

## Failure and repair times

- A failure is a stop whose first state is a fault of the machine, not a
  micro-stop, beginning in the period, with fault time inside a planned
  window; the others are listed apart.
- MTTR (mean time to restoration in IEC usage, often: to repair; the
  nearest ISO 22400 figure) = fault minutes of the failures that ended /
  their number: the fault's whole length, breaks included, read past the
  period end; waiting after the fault is not repair. The rough MTTR of `downtime-losses.md` counts the whole stop
  inside the period; `maintenance-reliability.md` has the figure that spans
  gaps in the data. Name which one.
- MOTBF = run time / failures: the nearest ISO 22400-2 figure to the MTBF of
  `downtime-losses.md`; public descriptions differ on whether it counts run
  time or busy time. Without a failure: "no failure in X hours of run
  time", its run time kept in pooled sums. An unclassified stop state makes
  both not computable.

## Further figures, without SQL here

Each as one public description gives it; say so when quoting one.

- Throughput rate = an order's quantity / its execution time (order start
  to end); allocation ratio = busy time / execution time. For one machine
  from its order intervals; across machines they need the order's route
  with transport and queue times.
- Net equipment effectiveness = (run + setup time) / planned busy time x
  effectiveness x quality ratio.
- Equipment load ratio = quantity / capacity: ask what capacity is (planned
  time / ideal cycle time only if the user agrees).
- Corrective maintenance ratio = corrective / (corrective + preventive)
  maintenance time: approximated by failure repair time against a planned
  maintenance state; ask which state that is, and say it is approximate.

These need data a machine does not report; say what to add: worker
efficiency (staff times); actual to planned scrap ratio (planned scrap) and
fall off ratio (quantities through all operations); inventory and loss
ratios (stock and material balances); energy (`energy-performance.md`) and
capability indices (`process-quality.md`).
