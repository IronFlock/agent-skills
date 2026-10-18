"""What widget-markdown makes of its Markdown body: the markup that renders broken.

widget-markdown fills a `{{name}}` placeholder with the value of the `data` entry
whose `label` is `name`, always as plain text, and renders the rest with marked
(CommonMark with the GitHub extensions). Where a placeholder works depends on the
version:

- From 1.0.14 on, it works in text, code, link addresses and HTML attribute
  values, and in the text of <style>, <textarea> and <title>. The markup is
  sanitised: scripts, event handlers and javascript: links are removed. In CSS
  (a style attribute, a <style> element, an SVG paint) a value must be a plain
  CSS value (is_css_value), or it is left out.
- Up to 1.0.13, every placeholder became `<span class="md-var" …></span>` before
  marked ran, so it only worked in the text between tags. Inside a tag the span's
  quotes ended the attribute and the rest of the tag showed up as text; inside
  <style>, code or a link address it broke the CSS or the link, or showed as
  raw <span> markup.

For every version, check() also reports what marked does with HTML: Markdown
inside an HTML block (from a line that starts with a tag to the next blank line)
is not parsed, so `**bold**` keeps its asterisks, and after a blank line a line
indented by four spaces or more is a code block, even inside an HTML element.
And a placeholder without a data entry renders as nothing, while markup in a
value shows as text. Each rule was checked against marked 16, the version the
widget ships.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Any

PLACEHOLDER = re.compile(r"\{\{([^}]+)\}\}")

#: The first widget-markdown release that fills placeholders outside plain text
#: and sanitises the markup.
FILLS_ATTRIBUTES_SINCE = (1, 0, 14)

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])(?:[ \t]|$)")
_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
# The HTML block starts of CommonMark, which marked follows. These five run to an
# end marker; a block-level tag (_BLOCK_START) and a tag alone on its line
# (_LONE_TAG, which cannot interrupt a paragraph) run to the next blank line.
_RAW_BLOCKS = [
    (re.compile(r"^ {0,3}<(?:script|pre|style|textarea)(?:[\s>]|$)", re.I), re.compile(r"</(?:script|pre|style|textarea)>", re.I)),
    (re.compile(r"^ {0,3}<!--"), re.compile(r"-->")),
    (re.compile(r"^ {0,3}<\?"), re.compile(r"\?>")),
    (re.compile(r"^ {0,3}<![A-Za-z]"), re.compile(r">")),
    (re.compile(r"^ {0,3}<!\[CDATA\["), re.compile(r"\]\]>")),
]
_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
    "dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|"
    "hr|html|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|"
    "search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_BLOCK_START = re.compile(rf"^ {{0,3}}</?(?:{_BLOCK_TAGS})(?=[\s/>]|$)", re.I)
_ATTRIBUTE = r"""(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:[^\s"'=<>`]+|'[^']*'|"[^"]*"))?)"""
_NOT_RAW = r"(?!(?:script|style|pre|textarea)\b)"
_LONE_TAG = re.compile(
    rf"^ {{0,3}}(?:<{_NOT_RAW}[A-Za-z][\w-]*{_ATTRIBUTE}*\s*/?>|</{_NOT_RAW}[A-Za-z][\w-]*\s*>)[ \t]*$", re.I
)

# Any tag in the text; quoted attribute values may hold '>' and line breaks.
_TAG = re.compile(r"""<(/?)([A-Za-z][\w:-]*)((?:[^<>"']|"[^"]*"|'[^']*')*)>""")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
# Elements whose content is text, not HTML.
_RAW_TEXT = re.compile(r"<(style|script|textarea|title)\b[^>]*>(.*?)(?:</\1\s*>|$)", re.I | re.S)
_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]*)\)")
_ATTRIBUTE_BEFORE = re.compile(r"""([A-Za-z_:][\w.:-]*)\s*=\s*(?:"[^"]*|'[^']*|[^\s"'>]*)$""")
_HANDLER = re.compile(r"""(?:^|\s)(on[a-z]+|srcdoc)\s*=""", re.I)
_SCRIPT_URL = re.compile(r"""(?:^|\s)(?:href|src|action|formaction|xlink:href)\s*=\s*["']?\s*javascript:""", re.I)
_INLINE_MARKDOWN = re.compile(r"\*\*[^\s*](?:[^*\n]*[^\s*])?\*\*|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]*\)")
_BLOCK_MARKDOWN = re.compile(r"^ {0,3}(#{1,6}|[-+*]|\d{1,9}[.)])[ \t]+\S")
_MARKUP = re.compile(r"<[A-Za-z/!]")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_STYLING = {"style", "class", "color", "bgcolor", "background"}
# Attributes whose value is CSS: style, and the SVG paints that take url().
_CSS_ATTRIBUTES = {"style", "fill", "stroke", "filter", "mask", "clip-path", "marker-start", "marker-mid", "marker-end", "cursor"}
# A value the widget accepts in CSS (its isCssValue): keywords, numbers with units,
# hex colours, lists of these, or one colour function. ASCII letters only, as in
# the widget's JavaScript.
_CSS_VALUE = re.compile(r"^[A-Za-z0-9_\s#%.,+-]*$")
_CSS_COLOR = re.compile(r"^\s*(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\([A-Za-z0-9_\s#%.,+/-]*\)\s*$", re.I)


@dataclass(frozen=True)
class Finding:
    level: str  # "error": renders broken; "warn": works, but probably not as meant
    message: str
    path: tuple = ("markdown",)  # below the widget's chartconfig


def fills_attributes(version: str | None) -> bool:
    """Whether this widget-markdown version fills placeholders outside plain text.
    An unknown version counts as the latest."""
    if not version:
        return True
    parts = [int(m.group()) if (m := re.match(r"\d+", p)) else 0 for p in version.split(".")[:3]]
    return tuple(parts) >= FILLS_ATTRIBUTES_SINCE


def is_css_value(value: str) -> bool:
    """Whether the widget puts this value into CSS rather than leaving it out."""
    return bool(_CSS_VALUE.match(value) or _CSS_COLOR.match(value))


def check(markdown: str, data: Any = None, version: str | None = None) -> list[Finding]:
    """Findings for a widget-markdown body and its `data` entries.

    Pass both as the widget receives them, with `$str:` constants decoded. `data`
    is the list of {label, value} entries. When the list or a label comes from a
    binding, the labels cannot be known, and the label checks are skipped.
    `version` is the widget-markdown version that renders it (None: the latest).
    """
    fills = fills_attributes(version)
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)

    def line_no(offset: int) -> int:
        return bisect.bisect_right(starts, offset)

    def line_end(i: int) -> int:
        return starts[i] + len(lines[i])

    kinds = _line_kinds(lines)
    findings: list[tuple[int, Finding]] = []

    def report(offset: int, message: str, level: str = "error", path: tuple = ("markdown",)) -> None:
        findings.append((offset, Finding(level, f"line {line_no(offset)}: {message}", path)))

    def placeholder(m: re.Match) -> str:
        return "{{" + m.group(1).strip() + "}}"

    masked = list(text)

    def mask(start: int, end: int) -> None:
        for k in range(start, end):
            if masked[k] != "\n":
                masked[k] = " "

    # Code: indented and fenced blocks, and code spans in paragraphs.
    code: list[tuple[int, int, str]] = []
    indented_runs: list[tuple[int, int]] = []
    for kind, first, last in _runs(kinds):
        start, end = starts[first], line_end(last)
        if kind == "code":
            indented_runs.append((first, last))
            code.append((start, end, "a code block"))
        elif kind == "fence":
            code.append((start, end, "a code block"))
        elif kind == "text":
            code += [(start + s, start + e, "a code span") for s, e in _code_spans(text[start:end])]
    for start, end, _ in code:
        mask(start, end)
    hidden = [(m.start(), m.end()) for m in _COMMENT.finditer("".join(masked))]
    for start, end in hidden:
        mask(start, end)

    raw: list[tuple[int, int, str]] = []
    for m in _RAW_TEXT.finditer("".join(masked)):
        name = m.group(1).lower()
        raw.append((m.start(2), m.end(2), name))
        if name == "script":
            report(
                m.start(),
                "<script> never runs in widget-markdown: from 1.0.14 on it is removed, and before that the browser "
                "did not run scripts inserted as markup.",
            )
        mask(m.start(2), m.end(2))
    body = "".join(masked)  # code, comments and raw text blanked out
    tags = list(_TAG.finditer(body))

    # Event handlers and javascript: links in the author's markup.
    for tag in tags:
        handler = _HANDLER.search(tag.group(3))
        if handler or _SCRIPT_URL.search(tag.group(3)):
            what = f"the {handler.group(1).lower()} attribute" if handler else "a javascript: address"
            report(
                tag.start(),
                f"<{tag.group(2)}> has {what}. widget-markdown runs no code from its markup: from 1.0.14 on it removes "
                "event handlers, srcdoc and javascript: links.",
            )
    for kind, first, last in _runs(kinds):
        if kind == "text":
            for link in _LINK.finditer(body, starts[first], line_end(last)):
                if link.group(1).strip().lower().startswith("javascript:"):
                    report(link.start(), "a javascript: link never runs: from 1.0.14 on widget-markdown removes it.")

    # Indented runs that hold HTML, or sit inside an open element: HTML shown as text.
    html_as_code: set[tuple[int, int]] = set()
    for first, last in indented_runs:
        start, end = starts[first], line_end(last)
        open_element = _open_element(tags, start)
        if lines[first].lstrip().startswith("<") or (open_element and PLACEHOLDER.search(text, start, end)):
            html_as_code.add((start, end))
            inside = f", inside the <{open_element}> opened before it" if open_element else ""
            report(
                start,
                "this line follows a blank line and is indented by 4 or more spaces, so Markdown renders it as a code "
                f"block{inside}: its HTML shows on the board as raw text. Inside HTML, leave out the blank lines or "
                "indent by less than 4 spaces.",
            )

    def region(offset: int, regions: list) -> Any:
        return next((r for r in regions if r[0] <= offset < r[1]), None)

    live: list[re.Match] = []  # placeholders that show a value
    named: set[str] = set()  # every name a placeholder outside comments uses
    css: set[str] = set()  # names whose value lands in CSS
    for m in PLACEHOLDER.finditer(text):
        if region(m.start(), hidden):
            continue
        named.add(m.group(1).strip())
        in_code = region(m.start(), code)
        if in_code and not fills:
            if not any(s <= m.start() < e for s, e in html_as_code):
                report(
                    m.start(),
                    f"{placeholder(m)} is inside {in_code[2]}. Up to widget-markdown 1.0.13 every {{{{…}}}} becomes a "
                    "<span> element, in code too, and Markdown shows code literally, so the raw <span …> markup appears "
                    f"instead of the value. For a monospaced value write <code>{placeholder(m)}</code>.",
                )
            continue
        live.append(m)
        in_raw = region(m.start(), raw)
        if not in_raw or in_raw[2] == "script":  # the script itself is reported
            continue
        if fills:
            if in_raw[2] == "style":
                css.add(m.group(1).strip())
        else:
            effect = (
                "whose content is CSS, not HTML: it becomes broken CSS and is never filled"
                if in_raw[2] == "style"
                else "whose content is plain text, so the raw <span …> markup shows instead of the value"
            )
            report(m.start(), f"{placeholder(m)} is inside a <{in_raw[2]}> element, {effect}. {_newer_fills(version)}")

    # Placeholders inside tags.
    explained = color_hint = False
    for tag in tags:
        inside = [m for m in live if tag.start(3) <= m.start() < tag.end(3)]
        if not inside:
            continue
        attributes = []
        for m in inside:
            before = _ATTRIBUTE_BEFORE.search(text[tag.start(3) : m.start()])
            attributes.append(before.group(1).lower() if before else None)
        if fills:
            for m, attribute in zip(inside, attributes):
                if attribute is None:
                    report(
                        m.start(),
                        f"{placeholder(m)} stands where the <{tag.group(2)}> tag needs a name. A placeholder can fill "
                        "an attribute's value, never name a tag or an attribute.",
                    )
                elif attribute in _CSS_ATTRIBUTES:
                    css.add(m.group(1).strip())
            continue
        names = ", ".join(dict.fromkeys(placeholder(m) for m in inside))
        where = " and ".join(f"its {a} attribute" for a in dict.fromkeys(a for a in attributes if a)) or "the tag itself"
        message = f"{names} {'is' if len(inside) == 1 else 'are'} inside the <{tag.group(2)}> tag ({where})"
        if explained:
            message += " as well."
        else:
            explained = True
            message += (
                ". Up to widget-markdown 1.0.13 each {{…}} becomes a <span> element before the widget renders, which "
                "breaks the tag: the rest of it shows up on the board as text. There a placeholder works only in the "
                f"text between tags, so keep the attributes fixed. {_newer_fills(version)}"
            )
        if not color_hint and _STYLING & set(attributes):
            color_hint = True
            message += (
                " For a colour that follows the data on this version use widget-signal (colorMap), widget-gauge "
                "(zones) or widget-label (fontColor bound to a column that holds the colour)."
            )
        report(inside[0].start(), message)

    # Placeholders in link and image addresses (paragraphs only: HTML blocks have no links).
    for kind, first, last in _runs(kinds):
        if kind != "text" or fills:
            continue
        for link in _LINK.finditer(body, starts[first], line_end(last)):
            inside = [m for m in live if link.start(1) <= m.start() < link.end(1)]
            if inside:
                report(
                    inside[0].start(),
                    f"{placeholder(inside[0])} is in a link or image address. Up to widget-markdown 1.0.13 it becomes "
                    "a <span> element there, so Markdown no longer sees a link and shows the brackets as text. "
                    + _newer_fills(version),
                )

    # Markdown inside HTML blocks, which marked does not parse: first instance per block.
    bare = _TAG.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), body)  # tags blanked too
    for kind, first, last in _runs(kinds):
        if kind != "html":
            continue
        markers = {}
        for i in range(first, last + 1):
            block = _BLOCK_MARKDOWN.match(lines[i])
            if block and bare[starts[i] + block.start(1)] != " ":  # not part of a tag
                markers[i] = block.group(1)
        for i in range(first, last + 1):
            # A heading always; a list item only next to another, since a lone '- '
            # or '1. ' line reads the same as text.
            syntax = markers.get(i)
            if syntax and syntax[0] != "#" and i - 1 not in markers and i + 1 not in markers:
                syntax = None
            inline = _INLINE_MARKDOWN.search(bare[starts[i] : line_end(i)])
            if syntax or inline:
                shown = f"'{syntax} '" if syntax else f"`{inline.group()}`"
                report(
                    starts[i],
                    f"{shown} is Markdown inside an HTML block, which Markdown does not parse, so it shows literally. "
                    "An HTML block runs from a line that starts with a tag to the next blank line. Write HTML there "
                    "(<strong>, <em>, <a href>, <code>, <ul><li>), or end the block with a blank line before the Markdown.",
                )
                break

    # Placeholders against the data entries.
    labels: list[tuple[int, str]] = []
    known = True
    if isinstance(data, list):
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            label, value = item.get("label"), item.get("value")
            if isinstance(label, str):
                labels.append((i, label))
            elif label is not None:
                known = False
            if not isinstance(value, str):
                continue
            if isinstance(label, str) and label in css and not is_css_value(value):
                findings.append((-1, Finding(
                    "error",
                    f"{{{{{label}}}}} stands in CSS, where a value must be a plain CSS value such as #22c55e, "
                    f"rgb(34, 197, 94), 12px or bold; the widget leaves {value!r} out",
                    ("data", i, "value"),
                )))
            elif _MARKUP.search(value):
                findings.append((-1, Finding(
                    "error",
                    "a value is inserted as plain text, so its markup shows literally; put the markup in the markdown around the placeholder",
                    ("data", i, "value"),
                )))
    elif data is not None:
        known = False
    if known:
        first_use: dict[str, int] = {}
        for m in live:
            first_use.setdefault(m.group(1).strip(), m.start())
        defined = {label for _, label in labels}
        for name, offset in first_use.items():
            if name not in defined:
                report(offset, f"{{{{{name}}}}} has no data entry with the label '{name}', so it renders as nothing.")
        for i, label in labels:
            if label not in named:
                findings.append((-1, Finding("warn", f"no {{{{{label}}}}} in the markdown uses this entry", ("data", i, "label"))))

    return [f for _, f in sorted(findings, key=lambda pair: pair[0])]


def _newer_fills(version: str | None) -> str:
    """The hint for a board on a release that only fills placeholders in text."""
    return f"widget-markdown 1.0.14 and later fill it; this widget renders with {version}."


def _line_kinds(lines: list[str]) -> list[str]:
    """Each top-level line's block: blank, text, html, raw (an HTML block kind 1-5),
    fence or code (indented). Lines inside list items count as text."""
    kinds: list[str] = []
    state: Any = None  # None, "para", "html", ("fence", marker) or ("raw", end pattern)
    in_list = after_blank = False
    for line in lines:
        expanded = line.expandtabs(4)
        if isinstance(state, tuple) and state[0] == "fence":
            kinds.append("fence")
            m = _FENCE.match(expanded)
            if m and m.group(1)[0] == state[1][0] and len(m.group(1)) >= len(state[1]) and not expanded[m.end():].strip():
                state = None
            continue
        if isinstance(state, tuple) and state[0] == "raw":
            kinds.append("raw")
            if state[1].search(line):
                state = None
            continue
        if not expanded.strip():
            kinds.append("blank")
            state, after_blank = None, True
            continue
        if state == "html":
            kinds.append("html")
            continue
        indent = len(expanded) - len(expanded.lstrip(" "))
        if in_list and after_blank and indent < 2 and not _LIST_ITEM.match(expanded):
            in_list = False
        after_blank = False
        if in_list and indent >= 2:
            kinds.append("text")
            continue
        if indent >= 4:
            kinds.append("text" if state == "para" else "code")
            continue
        kind = _block_start(expanded, state)
        if kind == "fence":
            state = ("fence", _FENCE.match(expanded).group(1))
        elif isinstance(kind, tuple):
            state, kind = kind, "raw"
        elif kind == "raw":
            state = None
        elif kind == "html":
            state = "html"
        else:
            state = None if _HEADING.match(expanded) else "para"
            if _LIST_ITEM.match(expanded):
                in_list = True
        kinds.append(kind)
    return kinds


def _block_start(line: str, state: Any) -> Any:
    """"fence", "raw" (a one-line raw block), ("raw", end) (an open one), "html" or "text"."""
    if _FENCE.match(line):
        return "fence"
    for start, end in _RAW_BLOCKS:
        m = start.match(line)
        if m:
            return "raw" if end.search(line, m.end()) else ("raw", end)
    if _BLOCK_START.match(line) or (state != "para" and _LONE_TAG.match(line)):
        return "html"
    return "text"


def _runs(kinds: list[str]):
    """(kind, first line, last line) for each run of consecutive lines of one kind."""
    first = 0
    for i in range(1, len(kinds) + 1):
        if i == len(kinds) or kinds[i] != kinds[first]:
            yield kinds[first], first, i - 1
            first = i


def _code_spans(paragraph: str) -> list[tuple[int, int]]:
    """CommonMark code spans: a backtick run up to the next run of the same length."""
    runs = [(m.start(), m.end()) for m in re.finditer(r"`+", paragraph)]
    spans, j = [], 0
    while j < len(runs):
        start, end = runs[j]
        k = next((k for k in range(j + 1, len(runs)) if runs[k][1] - runs[k][0] == end - start), None)
        if k is None or (start and paragraph[start - 1] == "\\"):
            j += 1
            continue
        spans.append((start, runs[k][1]))
        j = k + 1
    return spans


def _open_element(tags: list, offset: int) -> str | None:
    """The innermost element still open at `offset`, if any."""
    stack: list[str] = []
    for tag in tags:
        if tag.start() >= offset:
            break
        name = tag.group(2).lower()
        if tag.group(1):
            if name in stack:
                del stack[len(stack) - 1 - stack[::-1].index(name):]
        elif name not in _VOID and not tag.group(3).rstrip().endswith("/"):
            stack.append(name)
    return stack[-1] if stack else None
