<!-- Adapted from the claude-for-manufacturing plugin, version 1.0.0, by Anthropic, under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten for machine data in SQL tables. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-production-figures (IronFlock/ai-plugins), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# Downtime and loss ranking

Stops of machines: planned and unplanned, ranked by minutes and by count,
reason codes, MTTR and MTBF, the losses of OEE in minutes, prices. The
definitions are in `oee.md`, deriving stops from rows in
`machine-data-sql.md`.

## Terms

- **Stop** (Stillstand): a period in which the machine does not produce.
  **One stop is one continuous period in any state the plant counts as a
  stop** (FAULT then WAIT is one stop), however many rows it spans; a gap
  in the data ends it. Counting rows or state values inflates the frequency.
- **Planned stop** (ISO 22400-2: planned down time): a break, planned
  maintenance, and whatever else the plant defines as planned. Shown on its
  own, never in the ranking of unplanned stops and never as an availability
  loss.
- **Unplanned stop**: a breakdown (Störung), waiting for material or an
  operator, an adjustment, a changeover the plant does not count as planned.
- **Micro-stop** (Kurzstillstand): a stop shorter than the plant's
  threshold. A performance loss; rank it apart, by count: each lasts only
  a short time, so even many of them vanish in a ranking by minutes.

## Rank both ways, always

Rank stops by total minutes and by number of stops, side by side, over the
same period and the same machines. One four-hour breakdown and forty
six-minute jams can add to the same minutes: the first points at a component
or a missing spare part, the second at an adjustment, a setting or a design
fault, and the second is usually easier to fix. A single ranking hides the
problem it does not sort by.

Per reason and per machine also give:

- **Mean stop length** = stop minutes / number of the stops whose minutes
  are counted (not those kept out of the minutes, below); for
  breakdowns this is a rough **MTTR** (mean time to restoration in IEC
  usage, often called mean time to repair); the exact figure, ending with
  the fault and spanning gaps in the data, is in
  `maintenance-reliability.md`.
- **MTBF** (mean time between failures) = run time / number of breakdowns;
  the nearest ISO 22400-2 figure is the mean operating time between
  failures. Name what counts as a breakdown; a micro-stop is not one.
- Failures, repair times and what machine data cannot show about them:
  `maintenance-reliability.md`.
- For a ranking of machines ("which machines hurt us most"): minutes,
  stops, mean stop length, the top reason and its share. High minutes with few stops,
  many stops with few minutes, and high on both are three different
  findings; say which a machine is.

## Reason codes

- Before ranking by reason, count the stops and minutes without a usable
  reason (empty, "Other", "Sonstige", "unknown") and state that share first:
  "18 of 39 stops (46%) have no usable reason". Then rank the named reasons
  only, saying the picture is incomplete by that share. "No reason" at the
  top of a ranking tells nobody what to fix, and a large share is itself a
  finding worth fixing.
- A code is translated into words only from a table or from the user,
  never guessed.
- A stop's minutes go to the reason of its first row: a convention, so say
  it. The alternative: each part's minutes to its own reason, the stop
  counted once under its first reason.

## Edges of the period and bad rows

- A stop that runs across the start or end of the period contributes only
  its minutes inside the period. It counts as one stop in the period where
  it began, so that sums over periods do not count it twice, and shows its
  true start; say so.
- A stop still going on is one stop with its minutes so far, marked as
  ongoing ("at least 47 minutes"), not a closed stop.
- A row whose end lies before its start, or whose stated duration disagrees
  with its start and end, has no trustworthy minutes: count it as a stop,
  keep it out of the minutes, and list it.
- Two rows for the same machine and start are a finding; never count them
  twice silently.

## The losses of OEE in minutes

All losses can be shown in one unit, minutes, which adds up:

```text
known time (planned, with usable state data) - stops    = run time
run time - ideal cycle time x total count               = speed loss and micro-stops
ideal cycle time x (total count - good count)           = quality loss
known time - all three losses = ideal cycle time x good count (fully productive time)
```

Example: planned 450 min, stops 45, ideal cycle time 1.0 min, total 360,
good 342: availability loss 45, performance loss 405 - 360 = 45, quality
loss 18; 450 - 108 = 342 fully productive minutes.

The six classic losses (from TPM, not ISO 22400) and their parts:
breakdowns and changeovers (Störungen, Rüsten) lower availability;
micro-stops and reduced speed (Kurzstillstände, Geschwindigkeitsverluste)
lower performance; start-up rejects and production rejects with rework
(Ausschuss, Nacharbeit) lower quality.

## Prices

- A loss is priced only with a rate the user gives or the data holds (cost
  per hour of stop, cost per scrapped part), and the rate's source is named
  next to the figure. Without one, report minutes and parts and say they are
  not priced. Never use a typical, industry or example rate; a number named
  only to reject it gets repeated.
- Scrap priced at standard cost is an estimate, and says so.
- Never add quantities of different units (pieces, kg, boxes); report each
  in its unit.
