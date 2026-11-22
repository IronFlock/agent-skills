#!/usr/bin/env python3
"""Contrast and file form of the board presets, computed from the text.

    python3 tests/preset_checks.py

Reads the presets from references/board-design.md ("Pick a look": the table
of style values, state colours and the first series colour, and the sentence
with the contrast claim) and checks, for every preset:

- its style, in the file form, against the `style` of the board schema
  (schemas/board-template/v1.yml): every key and value must be allowed; a
  `glass` tile needs a see-through tile colour and a gradient or a picture;
- text on the tile 11:1 or better, each state colour on the tile 3:1 or
  better (WCAG 2.x contrast ratio), the floors the claim names. A see-through
  tile is first laid over the reference the claim names for it ("no lighter
  than"), which must be the preset's own `background_color`; the paragraph on
  the preset must name the same reference, say that nothing that carries a
  state goes outside a tile, and name an opaque preset to take instead;
- its series colours: the 2nd is the text colour; the 1st reads on the tile
  at 5:1 or better, stays apart in lightness from the 2nd (1.8:1 or better
  for normal vision and simulated protanopia and deuteranopia), and stays
  clear of each state colour (CIE76 delta E 18 or more for normal vision and
  simulated protanopia, deuteranopia and tritanopia; Machado, Oliveira and
  Fernandes 2009, severity 1.0, in linear RGB). The floors 1.8 and 18 are not
  derived from a standard: they were set just under the lowest values of the
  three presets released first (1.88, and 18.8 for control-room's ok under
  tritanopia);
- the series table of board-charts.md holds the same colours;
- the Delete red of board-interaction.md: one per preset, in the hue of the
  preset's alarm colour, 3:1 or better on the form's surface and on its
  dialog, for a form in the preset's tile and in a transparent tile. The
  surface is the tile colour laid over `background_color` (over white), as
  widget-form computes it; the dialog raises a surface darker than relative
  luminance 0.18 by 16% white;
- the presets written out in the file form in board-layout-style.md
  ("Presets") hold the table's values.

Then every case of NEGATIVE plants one mistake into a copy of the texts and
must be reported.

Needs PyYAML and jsonschema (the `just test` environment).
"""

from __future__ import annotations

import colorsys
import copy
import re
import sys
from pathlib import Path
from typing import Callable

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parent / "plugins/ironflock-dev/skills/ironflock-templates"
REFS = SKILL / "references"
SCHEMA = SKILL / "schemas/board-template/v1.yml"

TEXT_ON_TILE = 11.0
STATE_ON_TILE = 3.0
SERIES_ON_TILE = 5.0
SERIES_LIGHTNESS = 1.8
SERIES_DELTA_E = 18.0
DELETE_RED = 3.0
#: How far (degrees of hue) the Delete red may be from the alarm colour.
RED_HUE = 20.0
STATES = ("ok", "warning", "alarm", "idle")
#: A value cell that is not a literal: what stands for it in the file form.
PLACEHOLDERS = {"the picture": "https://example.com/picture.jpg"}
HEXV = r"#[0-9a-fA-F]{6}"

HEX = re.compile(rf"^{HEXV}([0-9a-fA-F]{{2}})?$")
CVD = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}


# -- colour ----------------------------------------------------------------------


def _channels(colour: str) -> list[int]:
    h = colour.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lin(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _linear(colour: str, cvd: str | None = None) -> tuple[float, float, float]:
    rgb = [_lin(c) for c in _channels(colour)]
    if cvd is not None:
        m = CVD[cvd]
        rgb = [min(1.0, max(0.0, sum(m[i][j] * rgb[j] for j in range(3)))) for i in range(3)]
    return rgb[0], rgb[1], rgb[2]


def luminance(colour: str, cvd: str | None = None) -> float:
    r, g, b = _linear(colour, cvd)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str, cvd: str | None = None) -> float:
    la, lb = luminance(a, cvd), luminance(b, cvd)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def delta_e(a: str, b: str, cvd: str | None = None) -> float:
    def lab(colour: str) -> tuple[float, float, float]:
        r, g, b_ = _linear(colour, cvd)
        x = (0.4124 * r + 0.3576 * g + 0.1805 * b_) / 0.95047
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b_
        z = (0.0193 * r + 0.1192 * g + 0.9505 * b_) / 1.08883

        def f(t: float) -> float:
            return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

        return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))

    return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5


def over(top: str, below: str) -> str:
    """A #rrggbbaa colour laid over an opaque one, as a browser blends it."""
    h = top.lstrip("#")
    if len(h) == 6:
        return top
    alpha = int(h[6:8], 16) / 255
    return "#" + "".join(f"{round(alpha * t + (1 - alpha) * b):02x}"
                         for t, b in zip(_channels(top), _channels(below)))


def raised(surface: str) -> str:
    """The dialog surface widget-form draws on *surface*."""
    if luminance(surface) >= 0.18:
        return surface
    return "#" + "".join(f"{round(c * 0.84 + 255 * 0.16):02x}" for c in _channels(surface))


def opaque(colour: str, below: str) -> str:
    """*colour* laid over *below*, both laid over white (widget-form's
    surface: the tile over the board's background colour)."""
    return over(colour, over(below, "#ffffff"))


def hue(colour: str) -> float:
    r, g, b = (c / 255 for c in _channels(colour))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


# -- reading the texts -----------------------------------------------------------


def _flat(text: str) -> str:
    return " ".join(text.split())


def table(text: str, header: str) -> tuple[list[str], dict[str, list[str]]]:
    """The column heads and the rows of the table whose header line starts
    with *header*."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
    if start is None:
        raise ValueError(f"no table starting with {header!r}")

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    presets = cells(lines[start])[1:]
    rows: dict[str, list[str]] = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        row = cells(line)
        rows[row[0].strip("`")] = row[1:]
    return presets, rows


def _value(cell: str) -> object:
    """The file-form value of one table cell; None for `-` (left out)."""
    if cell == "-":
        return None
    if cell in PLACEHOLDERS:
        return PLACEHOLDERS[cell]
    token = cell.split()[0].strip("`")
    if re.fullmatch(r"\d+", token):
        return int(token)
    return token


def presets(design: str) -> dict[str, dict]:
    """Each preset of board-design.md: its style in the file form, its state
    colours and its series colours (the 2nd is its text colour)."""
    names, rows = table(design, "| Value |")
    grid = re.search(r"`columns` (\d+) and `rows` (\d+) in", design)
    out: dict[str, dict] = {}
    for i, name in enumerate(names):
        style: dict = {}
        for key, values in rows.items():
            if key in STATES or key.endswith("series"):
                continue
            value = _value(values[i])
            if value is None:
                continue
            if key == "theme.theme_name":
                style["theme"] = {"theme_name": value}
            else:
                style[key] = value
        if grid:
            style["columns"], style["rows"] = int(grid.group(1)), int(grid.group(2))
        out[name] = {
            "style": style,
            "states": {s: rows[s][i] for s in STATES if s in rows},
            "series": [rows["1st series"][i] if "1st series" in rows else None, style.get("text_color")],
        }
    return out


def claimed_reference(design: str, name: str) -> str | None:
    """The tone the contrast claim says *name*'s see-through tiles need behind
    them at most ("no lighter than")."""
    claim = _flat(design[design.find("In every preset the text reads"):])
    match = re.search(rf"`{re.escape(name)}` only where [^.;]*? no lighter than [^.;]*?`({HEXV})`", claim)
    return match.group(1) if match else None


def delete_reds(interaction: str) -> dict[str, str]:
    flat = _flat(interaction)
    sentence = flat[flat.find("The Delete button and its dialog"):]
    sentence = sentence[:sentence.find(". ")]
    reds: dict[str, str] = {}
    for colour, names in re.findall(rf"`({HEXV})` on ([a-z, -]+?)(?=, `|$)", sentence):
        for name in re.split(r",\s*|\s+and\s+", names):
            if name.strip():
                reds[name.strip()] = colour
    return reds


def layout_presets(layout: str) -> dict[str, dict]:
    """The presets written out in board-layout-style.md, "Presets"."""
    section = layout[layout.find("### Presets"):]
    found: dict[str, dict] = {}
    for block in re.findall(r"```yaml\n(.*?)```", section, re.S):
        name = re.search(r"^style:\s*#\s*(\S+)", block, re.M)
        states = dict(re.findall(rf"(\w+) '({HEXV})'", block.split("# states:", 1)[-1]))
        if name:
            found[name.group(1)] = {"style": yaml.safe_load(block)["style"], "states": states}
    return found


# -- the checks ------------------------------------------------------------------


def _see_through(name: str, look: dict, design: str, looks: dict[str, dict]) -> tuple[str | None, list[str]]:
    """The tone behind *name*'s see-through tiles, and what is wrong with how
    the text states that limit."""
    style = look["style"]
    reference = claimed_reference(design, name)
    if reference is None:
        return None, [f"{name}: see-through tiles, but the contrast claim names no reference for them"]
    problems = []
    if reference.lower() != str(style.get("background_color", "")).lower():
        problems.append(f"{name}: the claim's reference {reference} is not its background_color "
                        f"{style.get('background_color')}")
    start = design.find(f"`{name}` needs")
    paragraph = _flat(design[start:].split("\n\n", 1)[0]) if start >= 0 else ""
    if not re.search(rf"only over a picture no lighter than `{re.escape(reference)}`", paragraph):
        problems.append(f"{name}: its paragraph does not limit it to a picture no lighter than {reference}")
    if "draw nothing that carries a state outside a tile" not in paragraph:
        problems.append(f"{name}: its paragraph does not keep the states inside the tiles")
    instead = re.search(r"take `([a-z-]+)` when", paragraph)
    if not instead or instead.group(1) not in looks or len(looks[instead.group(1)]["style"].get(
            "tile_background_color", "")) != 7:
        problems.append(f"{name}: its paragraph names no preset with opaque tiles to take instead")
    return reference, problems


def check(texts: dict[str, str], schema: dict) -> list[str]:
    design = texts["design"]
    problems: list[str] = []
    try:
        looks = presets(design)
        chart_names, charts = table(texts["charts"], "| Series |")
    except (ValueError, IndexError, KeyError) as e:
        return [f"the preset tables cannot be read: {e}"]
    _, situations = table(design, "| Preset |")
    if list(situations) != list(looks):
        problems.append(f"the presets of the situation table {list(situations)} are not those of the "
                        f"values {list(looks)}")
    claim = _flat(design[design.find("In every preset the text reads"):])
    if not claim.startswith(f"In every preset the text reads at {TEXT_ON_TILE:g}:1 or better against the "
                            f"tiles and each state colour at {STATE_ON_TILE:g}:1 or better"):
        problems.append("the contrast claim of board-design.md is missing or names other floors")
    validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/style", "$defs": schema["$defs"]})
    reds = delete_reds(texts["interaction"])
    written = layout_presets(texts["layout"])
    for name, look in looks.items():
        style, states, series = look["style"], look["states"], look["series"]
        for error in validator.iter_errors(style):
            where = ".".join(str(p) for p in error.absolute_path) or "style"
            problems.append(f"{name}: {where}: {error.message}")
        colours = [style.get("text_color"), style.get("tile_background_color"), style.get("background_color"),
                   *states.values(), *series]
        bad = [c for c in colours if not (isinstance(c, str) and HEX.match(c))]
        if bad or len(states) != 4:
            problems.append(f"{name}: a colour is missing or not #rrggbb: {bad}")
            continue
        tile = style["tile_background_color"]
        see_through = len(tile) == 9 and tile[7:].lower() != "ff"
        if style.get("tile_style") == "glass" and not (
                see_through and (style.get("background_gradient_color") or style.get("background_image"))):
            problems.append(f"{name}: glass needs a see-through tile and a gradient or a picture behind it")
        behind = style["background_color"]
        if see_through:
            reference, found = _see_through(name, look, design, looks)
            problems += found
            if reference is None:
                continue
            behind = reference
        on_tile = opaque(tile, behind)
        text = style["text_color"]
        if ratio(text, on_tile) < TEXT_ON_TILE:
            problems.append(f"{name}: text {text} on tile {on_tile} is {ratio(text, on_tile):.2f}:1, under "
                            f"{TEXT_ON_TILE:g}:1")
        for state, colour in states.items():
            if ratio(colour, on_tile) < STATE_ON_TILE:
                problems.append(f"{name}: {state} {colour} on tile {on_tile} is {ratio(colour, on_tile):.2f}:1, "
                                f"under {STATE_ON_TILE:g}:1")
        first, second = series
        if ratio(first, on_tile) < SERIES_ON_TILE:
            problems.append(f"{name}: 1st series {first} on tile is {ratio(first, on_tile):.2f}:1, under "
                            f"{SERIES_ON_TILE:g}:1")
        for cvd in (None, "protanopia", "deuteranopia"):
            if ratio(first, second, cvd) < SERIES_LIGHTNESS:
                problems.append(f"{name}: the series {first} and {second} are {ratio(first, second, cvd):.2f}:1 "
                                f"apart in lightness ({cvd or 'normal vision'}), under {SERIES_LIGHTNESS:g}:1")
        for cvd in (None, *CVD):
            for state, colour in states.items():
                if delta_e(first, colour, cvd) < SERIES_DELTA_E:
                    problems.append(f"{name}: 1st series {first} is delta E {delta_e(first, colour, cvd):.0f} "
                                    f"from {state} {colour} ({cvd or 'normal vision'}), under "
                                    f"{SERIES_DELTA_E:g}")
        column = chart_names.index(name) if name in chart_names else None
        charted = [charts.get(k, [None] * len(chart_names))[column] for k in ("1st", "2nd")] if column is not None else []
        if charted != series:
            problems.append(f"{name}: board-charts.md's series colours {charted} differ from board-design.md's "
                            f"{series} (the 2nd is the text colour)")
        red = reds.get(name)
        if red is None:
            problems.append(f"{name}: board-interaction.md names no Delete red")
        else:
            if min(abs(hue(red) - hue(states["alarm"])), 360 - abs(hue(red) - hue(states["alarm"]))) > RED_HUE:
                problems.append(f"{name}: Delete red {red} is not in the hue of the alarm {states['alarm']}")
            # widget-form's surface: the tile colour (its own, or a transparent
            # one) over the board's background_color, never the picture
            for where, surface in (("tile", opaque(tile, style["background_color"])),
                                   ("transparent tile", opaque("#00000000", style["background_color"]))):
                for part, colour in (("form", surface), ("dialog", raised(surface))):
                    if ratio(red, colour) < DELETE_RED:
                        problems.append(f"{name}: Delete red {red} on the {part} of a {where} {colour} is "
                                        f"{ratio(red, colour):.2f}:1, under {DELETE_RED:g}:1")
        if name in written and (written[name]["style"] != style or written[name]["states"] != states):
            problems.append(f"{name}: board-layout-style.md writes it out with other values")
    for name in set(reds) - set(looks):
        problems.append(f"board-interaction.md names a Delete red for {name}, which is no preset")
    for name in set(written) - set(looks):
        problems.append(f"board-layout-style.md writes out {name}, which is no preset")
    return problems


def _sub(key: str, old: str, new: str, count: int = 1) -> Callable[[dict[str, str]], None]:
    def plant(texts: dict[str, str]) -> None:
        if old not in texts[key]:
            raise AssertionError(f"the planted text {old!r} is not in {key}")
        texts[key] = texts[key].replace(old, new, count)
    return plant


def _cell(row: str, column: int, value: str) -> Callable[[dict[str, str]], None]:
    """Replace one cell of a row of the values table of board-design.md
    (*column* counts the presets from 1)."""
    def plant(texts: dict[str, str]) -> None:
        lines = texts["design"].splitlines(keepends=True)
        i = next(i for i, line in enumerate(lines) if line.startswith(f"| {row} |"))
        cells = lines[i].rstrip("\n").split("|")
        cells[column + 1] = f" {value} "
        lines[i] = "|".join(cells) + "\n"
        texts["design"] = "".join(lines)
    return plant


def _both(*plants: Callable[[dict[str, str]], None]) -> Callable[[dict[str, str]], None]:
    def plant(texts: dict[str, str]) -> None:
        for p in plants:
            p(texts)
    return plant


def _flat_sub(key: str, old: str, new: str) -> Callable[[dict[str, str]], None]:
    """Replace *old* in *key* whatever the line breaks inside it."""
    def plant(texts: dict[str, str]) -> None:
        pattern = r"\s+".join(re.escape(w) for w in old.split())
        replaced, n = re.subn(pattern, new, texts[key], count=1)
        if not n:
            raise AssertionError(f"the planted text {old!r} is not in {key}")
        texts[key] = replaced
    return plant


LOBBY_CLAIM = "no lighter than its `background_color` `#1b2d4f`"
LOBBY_LIMIT = "only over a picture no lighter than `#1b2d4f`"

#: label, the mistake, a part of the finding it must produce.
NEGATIVE: list[tuple[str, Callable[[dict[str, str]], None], str]] = [
    ("dim text", _cell("`text_color`", 4, "#8a8580"), "night-shift: text #8a8580 on tile"),
    ("a light ok on grey", _cell("ok", 6, "#4ade80"), "scada-grey: ok #4ade80 on tile"),
    ("a state colour that is not a colour", _cell("alarm", 5, "red"), "showroom: a colour is missing"),
    ("an unknown tile style", _cell("`tile_style`", 5, "frosted"), "showroom: tile_style: 'frosted'"),
    ("an angle out of range", _cell("`background_gradient_angle`", 5, "400"), "showroom: background_gradient_angle"),
    ("a key the schema lacks", _sub("design", "| `grid_gap` |", "| `tile_shadow` | - | - | - | - | 4 | - | - | - |\n| `grid_gap` |"),
     "showroom: style: Additional properties are not allowed ('tile_shadow'"),
    ("a picture address that is no address", _sub("design", "| the picture |", "| picture |"), "lobby: background_image"),
    ("glass on an opaque tile", _cell("`tile_background_color`", 8, "#0f172a"), "lobby: glass needs a see-through tile"),
    ("series tables disagree", _cell("1st series", 7, "#2563eb"), "portal: board-charts.md's series colours"),
    ("a light 1st series", _both(_cell("1st series", 6, "#93c5fd"),
                                 _sub("charts", "| #4338ca |", "| #93c5fd |")), "scada-grey: 1st series #93c5fd on tile"),
    ("a 1st series like the ok state", _both(_cell("1st series", 3, "#166534"),
                                             _sub("charts", "| #2563eb | #1d4ed8 | #818cf8",
                                                  "| #2563eb | #166534 | #818cf8")),
     "daylight: 1st series #166534 is delta E"),
    ("a 2nd series that is not the text", _sub("charts", "| 2nd | #e2e8f0 | #1e293b", "| 2nd | #e2e8f0 | #334155"),
     "office: board-charts.md's series colours"),
    ("series too close in lightness", _both(_cell("1st series", 4, "#a5b4fc"),
                                            _sub("charts", "| #1d4ed8 | #818cf8 |", "| #1d4ed8 | #a5b4fc |")),
     "night-shift: the series #a5b4fc and #d6d3d1"),
    ("lobby over a light picture", _both(_cell("`background_color`", 8, "#5b7fb5"),
                                         _flat_sub("design", LOBBY_CLAIM, "no lighter than its `background_color` `#5b7fb5`"),
                                         _flat_sub("design", LOBBY_LIMIT, "only over a picture no lighter than `#5b7fb5`")),
     "lobby: text #f8fafc on tile"),
    ("lobby's reference is not its background", _flat_sub("design", LOBBY_CLAIM, "no lighter than `#0b1324`"),
     "lobby: the claim's reference #0b1324 is not its background_color"),
    ("lobby without its reference", _flat_sub("design", "in `lobby` only where the picture behind the tiles is " + LOBBY_CLAIM + ".",
                                              "in `lobby` too."),
     "lobby: see-through tiles, but the contrast claim names no reference"),
    ("lobby's limit reversed", _flat_sub("design", LOBBY_LIMIT, "only over a picture lighter than `#1b2d4f`"),
     "lobby: its paragraph does not limit it to a picture no lighter than #1b2d4f"),
    ("lobby's limit on another tone", _flat_sub("design", LOBBY_LIMIT, "only over a picture no lighter than `#5b7fb5`"),
     "lobby: its paragraph does not limit it to a picture no lighter than #1b2d4f"),
    ("lobby's states outside the tiles", _flat_sub("design", "draw nothing that carries a state outside a tile", "draw what you like"),
     "lobby: its paragraph does not keep the states inside the tiles"),
    ("lobby falls back to itself", _flat_sub("design", "take `showroom` when", "take `lobby` when"),
     "lobby: its paragraph names no preset with opaque tiles"),
    ("a claim with another floor", _sub("design", "the text reads at 11:1 or better", "the text reads at 7:1 or better"),
     "the contrast claim of board-design.md"),
    ("a Delete red that fails on the dark dialog",
     _flat_sub("interaction", "`#f87171` on control-room and night-shift", "`#f87171` on control-room, `#ef4444` on night-shift"),
     "night-shift: Delete red #ef4444 on the dialog of a tile"),
    ("lobby's red measured against its picture", _flat_sub("interaction", "`#fc8181` on lobby", "`#f87171` on lobby"),
     "lobby: Delete red #f87171 on the dialog of a transparent tile"),
    ("a Delete red that is no red", _flat_sub("interaction", "`#fc8181` on lobby", "`#fdba74` on lobby"),
     "lobby: Delete red #fdba74 is not in the hue of the alarm"),
    ("a preset without a Delete red", _flat_sub("interaction", "showroom, scada-grey and portal", "showroom and scada-grey"),
     "portal: board-interaction.md names no Delete red"),
    ("a written-out preset that drifted", _sub("layout", "    tile_style_strength: 40\n", "    tile_style_strength: 60\n"),
     "showroom: board-layout-style.md writes it out with other values"),
    ("a preset missing from the situations", _sub("design", "| scada-grey | panels beside", "| scada | panels beside"),
     "the presets of the situation table"),
]


def read_texts() -> dict[str, str]:
    return {key: (REFS / f"board-{key}.md").read_text(encoding="utf-8")
            for key in ("design", "charts", "interaction")} | {
        "layout": (REFS / "board-layout-style.md").read_text(encoding="utf-8")}


def main() -> int:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    texts = read_texts()
    failed = 0
    problems = check(texts, schema)
    looks = presets(texts["design"])
    print(f"{'ok  ' if not problems else 'FAIL'} presets: {len(looks)} ({', '.join(looks)})")
    for problem in problems:
        print(f"     {problem}")
    failed += bool(problems)
    missed: list[str] = []
    for label, plant, expected in NEGATIVE:
        planted = copy.deepcopy(texts)
        plant(planted)
        found = check(planted, schema)
        if not any(expected in f for f in found):
            missed.append(f"{label}: expected {expected!r}, got {found}")
    print(f"{'ok  ' if not missed else 'FAIL'} preset mistakes reported: {len(NEGATIVE) - len(missed)} of "
          f"{len(NEGATIVE)}")
    for line in missed:
        print(f"     {line}")
    failed += bool(missed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
