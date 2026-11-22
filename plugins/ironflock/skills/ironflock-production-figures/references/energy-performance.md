# Energy performance: indicators, baselines, base load and peaks

Energy figures of machines and plants from meter data. The SQL, with the
traps of meter data, is in `energy-performance-sql.md`; machine states, part
counters and planned time are in `machine-data-sql.md`.

## The standards

This text follows public descriptions of these standards, not their text:
say so when you name one. When a question goes beyond it (a clause, what an
auditor demands), say it is not held here and point to the document or the
certification body. Never say a figure conforms to a standard or is
calculated according to it.

- **ISO 50001**, Energy management systems: Requirements with guidance for
  use. What an organisation does to manage energy: review its energy use,
  choose indicators and baselines, set objectives, measure and show
  improvement. Applies when a plant runs or is certified to such a system.
- **ISO 50006**, Energy management systems: Evaluating energy performance
  using energy performance indicators and energy baselines. Guidance on
  choosing, building, using and maintaining indicators and baselines,
  relevant variables and normalisation. Applies whenever such figures are
  set up or checked, with or without ISO 50001.
- Others: ISO 50015 (measurement and verification of energy performance),
  ISO 50047 (determining energy savings), ISO 50002-1 (energy audits),
  ISO 50003 (bodies that certify ISO 50001).

**A management system standard sets no figure.** ISO 50001 defines no
formula, limit or target value; the organisation chooses its indicators and
targets. Asked whether a figure "meets ISO 50001", answer: no figure can;
the standard asks that suitable indicators and baselines exist, are kept up
to date and show improvement, and an audit judges the system, not a value.
Then offer the indicator with its baseline and relevant variables.

## Kinds of indicator

- **A measured value**: kWh per day, peak kW.
- **A ratio**: kWh per good part, per tonne, per machine hour (specific
  energy consumption, spezifischer Energieverbrauch). Name the divisor.
- **A model**: the energy the baseline expects for the actual relevant
  variables; the indicator is actual minus (or divided by) expected.

**A ratio misleads when part of the energy does not scale with output.** A
machine draws 200 kWh a day for heating, hydraulics and standby plus 0.5
kWh per part. At 1,000 parts it uses 700 kWh: 0.70 kWh per part. At 400
parts, 400 kWh: 1.00 kWh per part, 43% "worse" with no change in
efficiency. Report a ratio with its output beside it; when output varies,
compare against a model.

## The baseline

- **Period**: often a year, so that seasons and the product mix are in it;
  at least 30 complete periods (days or weeks) for a model, and covering the
  usual range of the variables.
- **Relevant variables**: what changes energy use regularly and can be
  measured: output, product mix, outdoor temperature (degree days),
  operating hours. **Static factors** usually stay fixed: equipment,
  building, shift system, process.
- **Model**: energy = fixed part + energy per unit x output, fitted on the
  periods of the baseline; more variables need a model with several. Report
  its parameters, r2, the number of periods and the range of each variable;
  use it only inside that range.
- **Normalise** when the variables differ between the periods: compare
  actual energy with what the model expects for the actual variables. Never
  normalise by a variable the measure itself changes (switching idle
  machines off cuts operating hours; per hour, the saving vanishes).
- **Redo the baseline** when a static factor changes (a machine added or
  removed, a new product or process, a meter moved), or when the model
  stops fitting without any measure. ISO 50001 and ISO 50006, as publicly
  described, ask for this too; the plant's own rule decides when.

## Comparing with the baseline

Per period: difference = actual - expected. The **cumulative difference** (CUSUM) adds them up in time: its slope
changes where performance changed; a flat line means as in the baseline.
The saving of a measure is the cumulative difference since it, if nothing
else changed: ask. A total is a saving only beyond its uncertainty, which
holds the scatter of the days and the error of the fitted line; the second
does not shrink with more days. The SQL computes the limit; below it, say
the difference is not shown. Beyond it, a verdict is still wrong about 1
time in 20, up to 1 in 12 when days depend on each other (then prefer
weekly periods): say so; never call a saving proven.

## Machine states, base load, load profile and peaks

- **Energy by machine state**: what a machine draws while it waits or is
  idle at night is the saving that needs no investment.
- **Load profile** (Lastgang): mean power per billing window.
- **Base load** (Grundlast): the power drawn when nothing produces: the
  median outside planned production, or a low percentile of all windows.
  Name the method.
- **Peak**: many grid tariffs bill the highest mean power over a window in a
  month or year; Germany's registering load metering, for example, uses
  clock quarter hours. Others use 30 or 60 minutes, a rolling window or kVA.
  Ask for the contract's window, period and price per kW. The billed peak is
  that of the connection: its main meter, never a sum of nested meters or of
  each meter's own peak. Lowering it saves only if every window above the
  new level is lowered: count them.

## Traps in meter data

Never sum or average power values for energy; never take a counter's
maximum minus minimum. Missing time is missing energy: report it, never
fill it. A meter that feeds several machines is split only by submeters. A
falling counter or negative power may be export (feed-in): ask, and never
report net as consumption. Never add gas in m³ to kWh, or other carriers,
without the user's factors.

## What the data can and cannot show

The data shows energy, power, profiles, energy per state and per part, and
models of measured variables. It does not hold prices (per kWh, per kW of
peak, by time of day), costs, CO2 emission factors, calorific values,
primary energy factors, the billing rules, or why consumption changed. Ask
for each value needed and name it with its source next to every figure it
affects. Never assume a price, a factor or a typical value; a number named
only to reject it gets repeated. Without them, report kWh and kW, unpriced.

## Combining

Sum energy and sum output over the same range, then divide; never average
ratios. A meter feeding several machines is one group with all their
parts. Pool parts only of machines side by side on one product; a line in
series is divided by the parts at its end. A meter with no data is named
"no data" beside the pooled figure, never counted as zero. A ratio holds
per product; across products, say it is a mix.

## German terms

Energy performance energiebezogene Leistung; energy performance indicator
(EnPI) Energieleistungskennzahl, commonly Energiekennzahl; energy baseline
(EnB) energetische Ausgangsbasis; relevant variable relevante Variable
(Einflussgröße); static factor statischer Faktor; base load Grundlast; peak
load Lastspitze, Spitzenlast; meter reading Zählerstand.
