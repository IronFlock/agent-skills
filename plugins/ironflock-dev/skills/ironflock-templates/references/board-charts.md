<!-- Adapted from the data-visualization skill of the data plugin, version 1.1.0, by Anthropic (anthropics/knowledge-work-plugins), under the Apache License, Version 2.0; this file is under the same licence. Changed by Record Evolution GmbH in 2026: rewritten for the widgets of IronFlock boards. The licence text and the notice are in LICENSE-APACHE-2.0.txt and NOTICE in the folder of the skill ironflock-templates (IronFlock/agent-skills), and at https://www.apache.org/licenses/LICENSE-2.0 -->
# Charts and figures

Each rule names its setting; one without a widget name is
widget-linechart's. Which widget for which data, and how constants are
written: board-design.md and widget-catalog.md.

## Chart or number

- Under about five points in the window: a card (board-design.md,
  "Figures are cards").
- An amount per hour or day is bars (`dataseries[].type: $str:bar`) with a
  fixed `queryParams.series.bucket` of that period, at most 2,000 buckets
  per window. Without one the bucket follows the tile's width: the count has
  no unit, and a line bridges the empty buckets, which are left out. Per
  shift: a transform with the shift times.

## Order

- Rank categories without an order of their own, largest first. Only a
  transform can (a category ref delivers names, descending). The widget
  gets its rows reversed and draws the first at the top
  (`axis.orientation: $str:horizontal`) or left. So: the top N in a
  subquery descending with LIMIT N, the outer query ascending,
  `queryParams.limit` above N, "Top 10" in the title, values on the bars
  (`dataseries[].styling.showValueLabels: $bool:true`).
- Hours and shifts: order the transform by their start time, descending;
  the hour of day breaks a night shift.

## Scale

- Bars, amounts and filled lines (`dataseries[].styling.fill`) start at
  zero: keep `axis.yAxisScaling` (and `yAxisScalingRight`) at the default
  `$bool:false`. A reading far from zero (oil near 70 °C) may leave it:
  `$bool:true`.
- Compare machines as bars on one axis: a category ref (`format.x` the
  machine, `queryParams.series.method` AVG or MAX) or a ranking transform.
  Separate or split line charts scale each on their own: they show the
  course, not which is higher (say so in `subTitle`).
- widget-gauge tiles of one figure share `dataseries[].sections.gaugeMinValue`
  and the last `dataseries[].sections.sectionLimits[].limit`.
- Every widget-heatmap sets `heatMap.min` and `heatMap.max` (else 0 and
  14), compared ones the same.
- Compared charts show one period: the same `windowPeriod`, `windowLength`
  and `nowMinusPeriods`, plus the same `timeStartParam` and `timeEndParam`
  under a calendar; a transform, the same period in its SQL. Raw rows beyond
  `queryParams.limit` lose their oldest part.

## How many

- Up to three series per chart, two on a wall screen, four when they are a
  total and its parts; up to about twelve categories, then the top N.
- A pivot (`dataseries[].data[].pivot`) draws its lines in one dash, told
  apart by colour alone. Split it, one chart per value, stacked
  (`dataseries[].advanced.chartName` with `#split#`,
  `axis.columnLayout: $bool:true`, ten rows each).

## Words

- `title` names what is measured, of what ("Output, line 2"), not a finding
  that live data can undo; `subTitle` the unit and the window's period
  ("parts per hour, last 24 h"). Both get cut at 300 px.
- `axis.yAxisLabel` and `axis.yAxisLabelRight` name the figure and its unit
  ("Temperature (°C)"); `axis.xAxisLabel` names the categories ("Cause") and
  stays empty on a time axis.

## Colour

- Series never take a state colour (board-design.md). Give every series
  `dataseries[].borderColor` and `dataseries[].backgroundColor`, the same
  colour; left empty, either shows the theme's (`dark`: red first). A
  restyle to another preset recolours every series.

Series colours (5:1 on the tiles, apart in lightness for red-green
colour-blind readers):

| Series | control-room | office | daylight |
|---|---|---|---|
| 1st | `#60a5fa` | `#2563eb` | `#1d4ed8` |
| 2nd | `#e2e8f0` | `#1e293b` | `#111827` |

- Never colour alone: line series differ by `dataseries[].styling.borderDash`:
  1st colour solid, 2nd dashed, 1st dotted; a total 2nd solid, its parts
  1st solid, dashed, dotted; a right-axis series dashed. Keep
  `axis.showLegend` on: the legend tells a series from a state.
- widget-doughnut: slices that are states take the state colours
  (`dataseries[].sections[][].color`), other parts the 1st colour and
  lighter tints, each with its `name`; beyond about five parts, bars.
- widget-heatmap: `heatMap.colors` from a faint tint of the 1st colour to
  the 1st, not green to red.
- A widget-table column of `columns[].type` `state` is only a coloured box:
  add a `string` column with the state.
