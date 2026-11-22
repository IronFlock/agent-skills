# Packaging, filling and bottling lines

What packaging, filling and bottling lines (Verpackungs-, Abfüllanlagen)
add to the core: their standards, the PackML states and their mapping, the
PackML tags, and line figures. OEE is in `oee.md`, stops in
`downtime-losses.md`, the queries in `packaging-lines-sql.md`.

## The standards

Written from public descriptions, not from the standards' text. A figure
here follows the definitions as publicly described; never say it conforms
to a standard. When a question needs a standard's exact text (a formula, a
time category's limits, an acceptance protocol), say this file lacks it.

- **ISA-TR88.00.02, Machine and Unit States: An Implementation Example of
  ISA-88.00.01**, known as PackML (developed by OMAC): states and modes of
  automated machines, and tags (PackTags) for status, counts and stop
  reasons. Applies wherever a controller reports PackML states.
- **DIN 8743** (Verpackungsmaschinen und Verpackungsanlagen: Kennzahlen),
  withdrawn and replaced by **EN 415-11, Safety of packaging machines, Part
  11: Determination of efficiency and availability**, which sets no safety
  requirements. Both define a time model, an output model, general figures
  (all losses) and technical figures (only the losses the machine or line
  itself causes), and how an acceptance run (Abnahmelauf) is held. They
  apply when a builder and a buyer agree on efficiency or availability.
- **Weihenstephan Standards** (WS Pack for beverage filling and packaging,
  WS Food, WS Bake, WS Brew, WS Sweets), kept at the Technical University
  of Munich: the data interface from machines to a production data system
  (states, modes, programs, counters; their own protocol or **OPC 40600,
  OPC UA for Weihenstephan Standards**), when a line is connected by WS.

## States, numberings and the mapping

| No. | PackML state | Category | Why |
| --- | --- | --- | --- |
| 6 | Execute, in Production mode | run | the only state that makes product |
| 11, 10, 12 | Held, Holding, Unholding | own stop | a condition in the machine (jam, reel out, operator task) |
| 8, 9, 1 | Aborting, Aborted, Clearing | own stop | a fault or emergency stop and its recovery |
| 2, 7, 15, 3, 4 | Stopped, Stopping, Resetting, Starting, Idle | own stop | stands at its own control |
| 16, 17 | Completing, Complete | own stop | the job ended; waiting for the next |
| 5, 13, 14 | Suspended, Suspending, Unsuspending | line stop | the line is not ready: starved or blocked |
| | any state in another mode | mode stop | not production |
| | outside the planned windows | not scheduled | from the plant's calendar, never from a state |
| | any other value | unknown | left out, listed, asked about |

Wait states: Stopped, Idle, Suspended, Held, Aborted, Complete.

**Numberings.** ISA-TR88.00.02 numbers the states 1 to 17 as above. OPC
30060 (tobacco machines) numbers the same states 0 to 16 (Stopped 0,
Execute 4, Complete 6, Suspended 12, Held 15). Only the value most frequent
while the counter rises tells them apart (6 or 4); a 0 or a missing 17
does not. When the data cannot tell, ask. Weihenstephan states are matched
by name only; any other value is unknown.

**Own stop** means a stop at this machine that the line did not cause. It
holds faults and the operator's or the order's stops (Idle, Stopped,
Complete): a machine's technical availability needs the stop reason to
tell them apart. OEE availability counts every stop alike.

**Modes.** `1 Production`, `2 Maintenance`, `3 Manual`; builders add more
from 4. Every non-production mode is a stop of the machine by default:
planned time comes from the plant's calendar. A plant may count a mode
(cleaning, a planned changeover) as planned time; name that choice, since
it hides any breakdown repaired in that mode. Weihenstephan programs
(`WS_Cur_Prog`: Production 1, Start Up 2, Run Down 4, Clean 8, Changeover
16, Maintenance 32, Break 64) work the same way, recognised by their WS_
name, not by the numbers (builders' modes start at 4 too). Break is planned
by default, since the plant set it; Start Up and Run Down are mode stops, a
choice to name, as they include waiting for product. `WS_Cur_Mode` (off,
manual, semi-automatic, automatic) is no PackML mode.

**Starved or blocked.** PackML marks the direction during Suspended with
the tags `EquipmentStarved` and `EquipmentBlocked`; WS has Lack (Mangel)
and Tailback (Stau). Lack or Tailback of a branch line is a category of
its own: its cause is not on the main line. Without tags the direction is
unknown. Suspended is optional: a machine without it may run empty in
Execute, a performance loss and a finding.

**Choices to state.** Held for refilling materials is an own stop; some
plants count it as logistics. WS external failure (air, power) is an own
stop for OEE, left out of technical availability.

## Tags for counts and stop reasons

- `ProdProcessedCount`: products made, good and defective (index 0 the
  main stream): the core's total count.
- `ProdDefectiveCount`: rejects. Good = processed minus defective, with the
  counter ranges crossed (processed low minus defective high, to high minus
  low); more defective than processed is a finding.
- Parts counted in a mode stop, a planned mode or an unknown state are
  no output: report them apart.
- `ProdConsumedCount`: materials used (caps, labels), not output.
- Each has `Count` (current job, reset) and `AccCount` (never reset): read
  `AccCount` as a counter, as `machine-data-sql.md` says.
- `StopReason`: the first event of the last stop (ID and value, meaning
  from the builder's list); read it at the stop's start.
- `MachDesignSpeed` (primary packages per minute, installed configuration)
  is the ideal rate only when the plant confirms it; `MachSpeed` and
  `CurMachSpeed` never are. `StateCumulativeTime` is a cross-check only.

Never add bottles, cases or pallets.

## Line figures

- **Output**: count the line at one point the plant names: the bottleneck
  (Engpassmaschine; usually the filler, Füller) or good units at the end.
  Never sum machines in series.
- **Line OEE** is the bottleneck's OEE with its line stops counted as stops;
  its ideal rate is the line's nominal output (Nennausbringung). It differs
  from each machine's own: buffers absorb a machine's short stops.
- **The cause of a line stop**, minute by minute: from a starved machine
  walk upstream, from a blocked one downstream, both ways when the
  direction is unknown. Pass machines that wait the same way or in an
  unknown direction, and machines that run without output (counter
  standing). The first other machine is the cause. A machine that runs and
  produces (a buffer feeds it), a blocked machine upstream or a starved one
  downstream ends the walk without a cause. A running machine without a
  counter is passed and the cause flagged: if it was only slow, a stopped
  machine further on is blamed; say so. Report minutes and waits per
  cause, with no cause, short waits and branch line, adding up to the
  waited time. Clocks are assumed in step; waits shorter than the
  micro-stop threshold are not searched. Buffers delay effects.
- **WS Pack** reports build on the same states (Störung, Mangel, Stau);
  ask the plant for a WS machine's data point list.
