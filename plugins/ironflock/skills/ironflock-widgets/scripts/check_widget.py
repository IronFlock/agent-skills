#!/usr/bin/env python3
"""Check an IronFlock widget repository against the widget standards.

    check_widget.py [REPO]               the widget repo (default: .)
    check_widget.py [REPO] --since HEAD  only what changed since a commit: findings HEAD did not have
    check_widget.py [REPO] --typecheck   also type-check src/ with the repo's TypeScript

Checks what IronFlock Studio relies on when it loads a widget, and the patterns
that broke widgets in production before: the package's identity and published
files, the build (the versioned element tag, externals that Studio's import map
provides), the component source, the config schema and the default config, the
generated types, the thumbnails, the docs, and a stale dist/.

Prints one finding per line as `LEVEL file[:line] path: message` and exits 1 if
there is any ERROR. An ERROR breaks the widget or the platform; a WARN breaks a
standard that can have a reason to bend, so read each one. The generated-types
check and --typecheck need the repo's node_modules (npm install) and node.

Standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# What the platform provides and reads
# --------------------------------------------------------------------------

# Studio's import map (the importmap script of Studio's page), October 2026. Keys ending in "/" map
# every specifier that starts with them. When a Studio checkout sits next to
# ironflock-widgets/, its live map is read instead.
IMPORT_MAP_SNAPSHOT: dict[str, str] = {
    "lit": "3.3.3",
    "lit/": "3.3.3",
    "lit-html": "3.3.3",
    "lit-html/": "3.3.3",
    "lit-element/": "4.1.1",
    "@lit/reactive-element": "2.1.2",
    "@lit/reactive-element/": "2.1.2",
    "@material/web/": "2.4.1",
    "echarts/core": "6.1.0",
    "echarts/charts": "6.1.0",
    "echarts/components": "6.1.0",
    "echarts/renderers": "6.1.0",
    "echarts/features": "6.1.0",
    "zrender/": "6.1.0",
    "tslib": "2.8.1",
    "tinycolor2": "1.6.0",
    "flatpickr": "4.6.13",
    "flatpickr/": "4.6.13",
    "lit-flatpickr": "0.4.1",
    "@open-wc/dedupe-mixin": "1.4.0",
    **{
        f"@vaadin/{pkg}{suffix}": "25.1.3"
        for pkg in (
            "grid",
            "component-base",
            "a11y-base",
            "vaadin-lumo-styles",
            "vaadin-themable-mixin",
            "checkbox",
            "text-field",
            "lit-renderer",
            "field-base",
            "input-container",
        )
        for suffix in ("", "/")
    },
    "@vaadin/vaadin-usage-statistics": "2.1.3",
    "@vaadin/vaadin-usage-statistics/": "2.1.3",
    "@vaadin/vaadin-development-mode-detector": "2.0.7",
    "@vaadin/vaadin-development-mode-detector/": "2.0.7",
}

# Packages that must come from the import map: they register custom elements,
# or their classes are compared with instanceof across modules.
MUST_BE_EXTERNAL = ("@material/web", "@vaadin/", "lit-flatpickr", "flatpickr", "echarts", "zrender")

# The events Studio listens for on a widget element.
HOST_EVENTS = {"nav-submit", "param-submit", "action-submit", "data-submit", "file-data-submit", "widget-defaults"}

# Widgets the platform registers (for aiSelection's notFor routing).
KNOWN_WIDGETS = {
    "widget-doughnut", "widget-embed", "widget-filter-calendar", "widget-filter-dropdown",
    "widget-form", "widget-gauge", "widget-heatmap", "widget-image", "widget-label",
    "widget-linechart", "widget-mapbox", "widget-markdown", "widget-navbar",
    "widget-navbutton", "widget-overlay", "widget-scada", "widget-sidenav",
    "widget-signal", "widget-statehistory", "widget-switch", "widget-table",
    "widget-textbox", "widget-toast", "widget-value",
}  # fmt: skip

SCHEMA_TYPES = {
    "string", "number", "boolean", "object", "array",
    "color", "textarea", "image", "targetColumn", "actionApp", "actionDevice",
}  # fmt: skip
BAD_TYPES = {
    "integer": ("WARN", "Studio's editor cannot store integer fields; use number and round in code"),
    "font": ("WARN", "Studio cannot edit font fields and the AI rejects their object shape"),
    "targetTable": ("ERROR", "the AI's widget validator crashes on it (UnknownType)"),
    "null": ("ERROR", "not a usable setting type"),
}
PROPERTY_KEYS = {
    "title", "description", "type", "order", "dataDrivenDisabled", "condition", "default",
    "enum", "enumLabels", "items", "properties", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "pattern", "minLength", "maxLength", "minItems",
    "maxItems", "format", "examples", "const", "additionalProperties", "$comment",
    "contentMediaType",
}  # fmt: skip
# What a textarea's contentMediaType can name: Studio's text dialog highlights these.
HIGHLIGHTED_MEDIA_TYPES = {"text/markdown"}
UNRENDERABLE = {"$ref", "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "definitions", "$defs"}
INERT = {
    "min": "nothing reads it; use minimum",
    "max": "nothing reads it; use maximum",
    "readOnly": "nothing implements it",
    "hidden": "nothing implements it",
}

AI_SCHEMA_BUDGET = 40_000  # characters of the schema + default config the AI gets in full
AI_ROUTING_BUDGET = 2_500  # characters of description + aiSelection, a share of a shared prompt


@dataclass
class Finding:
    level: str
    file: str
    line: int | None
    path: str
    message: str


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def strip_comments(code: str) -> str:
    """Blank out // and /* */ comments in TypeScript, keeping strings, template
    literals (also ones nested in ${...}) and the line numbers intact. CSS
    comments inside css`` templates are blanked too."""
    out: list[str] = []
    i, n = 0, len(code)
    # "tpl" while inside a template literal; an int (the depth of { } braces)
    # while in code. The bottom entry is the top-level code.
    stack: list[Any] = [0]
    while i < n:
        ch = code[i]
        top = stack[-1]
        if top == "tpl":
            if ch == "\\":
                out.append(code[i : i + 2])
                i += 2
            elif ch == "`":
                stack.pop()
                out.append(ch)
                i += 1
            elif code.startswith("${", i):
                stack.append(0)
                out.append("${")
                i += 2
            else:
                # A CSS comment, if it closes before the template literal does.
                end = code.find("*/", i + 2) if code.startswith("/*", i) else -1
                tick = code.find("`", i)
                if end != -1 and (tick == -1 or end < tick):
                    out.append(blank(code[i : end + 2]))
                    i = end + 2
                else:
                    out.append(ch)
                    i += 1
            continue
        if code.startswith("//", i):
            end = code.find("\n", i)
            end = n if end == -1 else end
            out.append(blank(code[i:end]))
            i = end
        elif code.startswith("/*", i):
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(blank(code[i:end]))
            i = end
        elif ch in "'\"":
            end = i + 1
            while end < n and code[end] != ch and code[end] != "\n":
                end += 2 if code[end] == "\\" else 1
            out.append(code[i : end + 1])
            i = end + 1
        elif ch == "/" and re.search(r"(^|[(,=:\[!&|?{};+\-*%<>~^]|\breturn|\btypeof)\s*$", code[max(0, i - 20) : i]):
            # A regular expression literal: copy it, so a `//` inside one
            # (/^zrender\//) is not read as a comment.
            end, in_class = i + 1, False
            while end < n and code[end] != "\n":
                if code[end] == "\\":
                    end += 2
                    continue
                if code[end] == "[":
                    in_class = True
                elif code[end] == "]":
                    in_class = False
                elif code[end] == "/" and not in_class:
                    break
                end += 1
            out.append(code[i : end + 1])
            i = end + 1
        elif ch == "`":
            stack.append("tpl")
            out.append(ch)
            i += 1
        else:
            if ch == "{":
                stack[-1] = top + 1
            elif ch == "}":
                if top == 0 and len(stack) > 1:
                    stack.pop()  # the end of a ${...}: back in the template literal
                else:
                    stack[-1] = max(0, top - 1)
            out.append(ch)
            i += 1
    return "".join(out)


def strictly_in(value: Any, values: list) -> bool:
    """JavaScript's values.includes(value): === semantics, so 0 is not false."""
    return any(type(value) is type(v) and value == v for v in values)


def find_node_binary() -> str | None:
    """node on PATH, or the newest nvm install (shells that skip nvm have none)."""
    found = shutil.which("node")
    if found:
        return found
    installs = sorted(
        Path.home().glob(".nvm/versions/node/v*/bin/node"),
        key=lambda p: [int(x) for x in re.findall(r"\d+", p.parent.parent.name)],
    )
    return str(installs[-1]) if installs else None


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def type_name(title: str) -> str:
    """The identifier json-schema-to-typescript derives from a schema title."""
    words = re.sub(r"(^\s*[^a-zA-Z_$])|([^a-zA-Z_$\d])", " ", title).split()
    name = "".join(w[:1].upper() + w[1:] for w in words)
    return name[:1].upper() + name[1:]


def resolve_import_map(specifier: str, imports: dict[str, str]) -> str | None:
    """The version the import map serves for a bare specifier, or None."""
    if specifier in imports:
        return imports[specifier]
    best = None
    for key in imports:
        if key.endswith("/") and specifier.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return imports[best] if best else None


def package_of(specifier: str) -> str:
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") else parts[0]


def major(version_range: str) -> set[int]:
    """Major versions a dependency range allows (roughly: each alternative's first number)."""
    majors = set()
    for alternative in version_range.split("||"):
        match = re.search(r"(\d+)", alternative)
        if match:
            majors.add(int(match.group(1)))
    return majors


def image_size(path: Path) -> tuple[str, int, int] | None:
    data = path.read_bytes()[:40]
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8 ":
            width, height = struct.unpack("<HH", data[26:30])
            return "webp", width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L":
            b = data[21:25]
            width = 1 + (((b[1] & 0x3F) << 8) | b[0])
            height = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return "webp", width, height
        if chunk == b"VP8X":
            return "webp", 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    return None


def find_node(root: dict, segments: list[str]) -> dict | None:
    """The schema node at a config path; "[]" steps into an array's items."""
    node: Any = root
    for segment in segments:
        if not isinstance(node, dict):
            return None
        if segment == "[]":
            node = node.get("items")
        else:
            props = node.get("properties")
            node = props.get(segment) if isinstance(props, dict) else None
    return node if isinstance(node, dict) else None


def relative_target(path: list[str], relative: str) -> list[str] | None:
    """Resolve a condition's relativePath the way Studio's editor does: start at
    the property itself, pop one segment per "..", ignore "." and empty parts."""
    target = list(path)
    for part in relative.split("/"):
        if part == "..":
            if not target:
                return None
            target.pop()
        elif part not in ("", "."):
            target.append(part)
    return target


# --------------------------------------------------------------------------
# The checker
# --------------------------------------------------------------------------


class WidgetCheck:
    def __init__(self, repo: Path, typecheck: bool, context: Path | None = None) -> None:
        self.repo = repo
        self.typecheck = typecheck
        # Where the repo really lives: its sibling widgets and the Studio checkout
        # are looked up from here (differs from repo when checking a git revision).
        self.context = (context or repo).resolve()
        self.findings: list[Finding] = []
        self.pkg = ""  # widget-<name>
        self.version = ""
        self.package: dict = {}
        self.schema: dict | None = None
        self.defaults: Any = None
        self.imports, self.import_map_source = self.load_import_map()

    # -- reporting ---------------------------------------------------------

    def add(self, level: str, file: str, message: str, path: str = "-", line: int | None = None) -> None:
        self.findings.append(Finding(level, file, line, path or "-", message))

    def error(self, file: str, message: str, path: str = "-", line: int | None = None) -> None:
        self.add("ERROR", file, message, path, line)

    def warn(self, file: str, message: str, path: str = "-", line: int | None = None) -> None:
        self.add("WARN", file, message, path, line)

    def read(self, relative: str) -> str | None:
        path = self.repo / relative
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None

    def load_import_map(self) -> tuple[dict[str, str], str]:
        studio = self.context.parent.parent / "studio" / "index.html"
        if studio.is_file():
            match = re.search(
                r'<script type="importmap">([\s\S]*?)</script>', studio.read_text(encoding="utf-8")
            )
            if match:
                try:
                    entries = json.loads(match.group(1)).get("imports", {})
                except json.JSONDecodeError:
                    entries = {}
                live = {}
                for key, url in entries.items():
                    versions = re.findall(r"@(\d+\.\d+\.\d+)", str(url))
                    live[key] = versions[-1] if versions else ""
                if live:
                    return live, str(studio)
        return IMPORT_MAP_SNAPSHOT, "snapshot"

    # -- package -----------------------------------------------------------

    def check_package(self) -> bool:
        text = self.read("package.json")
        if text is None:
            self.error("package.json", "missing; this is not a widget repository")
            return False
        try:
            self.package = json.loads(text)
        except json.JSONDecodeError as exc:
            self.error("package.json", f"not valid JSON: {exc}")
            return False
        pkg = self.package
        name = str(pkg.get("name", ""))
        match = re.fullmatch(r"@ironflock/(widget-[a-z0-9]+(?:-[a-z0-9]+)*)", name)
        if not match:
            self.error("package.json", f"name {name!r} must be @ironflock/widget-<name> in lower-case kebab case", "name")
            self.pkg = name.split("/")[-1] or "widget-unknown"
        else:
            self.pkg = match.group(1)
        if self.context.name != self.pkg:
            self.warn(
                "package.json",
                f"the folder is {self.context.name!r}; Studio's dev server finds a widget by "
                f"folder name, so check it out as {self.pkg}/",
                "name",
            )
        self.version = str(pkg.get("version", ""))
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.version):
            self.error("package.json", f"version {self.version!r} must be plain x.y.z: it becomes part of the element name", "version")
        if pkg.get("type") != "module":
            self.warn("package.json", 'set "type": "module"', "type")
        main = f"dist/{self.pkg}.js"
        if str(pkg.get("main", "")).lstrip("./") != main:
            self.error("package.json", f'main must be "{main}": the CDN serves it for the bare package URL Studio imports', "main")
        for field in ("browser", "jsdelivr", "unpkg"):
            if field in pkg and str(pkg[field]).lstrip("./") != main:
                self.error("package.json", f"{field} makes CDNs serve another file than main", field)
        if "exports" in pkg:
            self.warn("package.json", "exports is not needed; check that it still exposes main and package.json", "exports")
        files = [str(f).rstrip("/") for f in pkg.get("files") or []]
        for required in ("dist", "src"):
            if required not in files:
                self.error(
                    "package.json",
                    f'files must include "{required}": Studio and the AI load '
                    + ("the bundle" if required == "dist" else "src/definition-schema.json and src/default-data.json")
                    + " from the published package",
                    "files",
                )
        for thumbnail in ("thumbnail.webp", "thumbnail.png"):
            if thumbnail not in files:
                self.warn("package.json", f'files should include "{thumbnail}" for the palette', "files")
        scripts = pkg.get("scripts") or {}
        if not str(scripts.get("build", "")):
            self.error("package.json", "no build script", "scripts.build")
        types = str(scripts.get("types", ""))
        if "json2ts" not in types or "src/definition-schema.json" not in types:
            self.warn("package.json", "types should regenerate src/definition-schema.d.ts with json2ts", "scripts.types")
        expected = {
            "preversion": "release-preflight.sh",
            "version": "build",
            "postversion": "release-verify.sh",
            "release": "npm version patch",
        }
        for script, needle in expected.items():
            if needle not in str(scripts.get(script, "")):
                self.warn("package.json", f"the fleet's release pipeline expects {script} to run {needle!r}", f"scripts.{script}")
        for script in ("link", "unlink"):
            if "RESWARM/frontend" in str(scripts.get(script, "")):
                self.warn("package.json", f"{script} targets ../RESWARM/frontend, which no longer exists; Studio's dev server reads the sibling checkout", f"scripts.{script}")
        types_field = pkg.get("types") or pkg.get("typings")
        build = self.build_config()
        if types_field and build and build[0].startswith("vite") and "dts(" not in build[1]:
            self.warn("package.json", f"types points at {types_field}, which a Vite build without vite-plugin-dts never produces; drop the field", "types")

        npmrc = self.read(".npmrc") or ""
        if not re.search(r'^\s*tag-version-prefix\s*=\s*""\s*$', npmrc, re.M):
            self.error(".npmrc", 'needs tag-version-prefix="": releases are tagged with the bare version, which release-verify.sh and CI expect')
        workflows = sorted(p for p in (self.repo / ".github" / "workflows").glob("*.y*ml"))
        if not workflows:
            self.error(".github/workflows", "no workflow: nothing publishes a release tag to npm")
        else:
            if len(workflows) > 1:
                self.warn(".github/workflows", "more than one workflow; npm's trusted publisher is bound to one workflow file")
            flow = workflows[0].read_text(encoding="utf-8")
            where = workflows[0].relative_to(self.repo).as_posix()
            if "id-token: write" not in flow:
                self.error(where, "needs `permissions: id-token: write` for npm trusted publishing")
            if "npm publish" not in flow:
                self.error(where, "never runs npm publish")
            if re.search(r"npm (install|i)\b", flow) and "npm ci" not in flow:
                self.warn(where, "use npm ci, so CI builds exactly the lockfile")
        for script in ("release-preflight.sh", "release-verify.sh"):
            if script in json.dumps(scripts) and not (self.repo / "scripts" / script).is_file():
                self.error(f"scripts/{script}", "package.json runs it, but it is missing")
        lock = self.read("package-lock.json")
        if lock is None:
            self.warn("package-lock.json", "missing; CI installs with npm ci")
        else:
            try:
                locked = json.loads(lock)
                if locked.get("name") != pkg.get("name") or locked.get("version") != pkg.get("version"):
                    self.warn("package-lock.json", "name or version differ from package.json; run npm install")
            except json.JSONDecodeError:
                self.error("package-lock.json", "not valid JSON")
        return True

    # -- build -------------------------------------------------------------

    def build_config(self) -> tuple[str, str] | None:
        for name in ("vite.config.ts", "vite.config.js", "vite.config.mjs", "rollup.config.js", "rollup.config.mjs"):
            text = self.read(name)
            if text is not None:
                return name, text
        return None

    def externals(self, config: str) -> list[re.Pattern | str]:
        code = strip_comments(config)
        match = re.search(r"external\s*:\s*\[", code)
        if not match:
            return []
        i, depth, in_regex = match.end(), 1, False
        start = i
        while i < len(code) and depth:
            ch = code[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "/" and not in_regex and code[i - 1] in "[, \n\t(":
                in_regex = True
            elif ch == "/" and in_regex:
                in_regex = False
            elif not in_regex and ch == "[":
                depth += 1
            elif not in_regex and ch == "]":
                depth -= 1
            i += 1
        body = code[start : i - 1]
        result: list[re.Pattern | str] = []
        for regex in re.findall(r"/((?:\\.|[^/\n])+)/[a-z]*", body):
            try:
                result.append(re.compile(regex.replace("\\/", "/")))
            except re.error:
                pass
        result += re.findall(r"""['"]([^'"]+)['"]""", body)
        return result

    @staticmethod
    def is_external(specifier: str, externals: list[re.Pattern | str]) -> bool:
        for external in externals:
            if isinstance(external, str):
                if specifier == external:
                    return True
            elif external.search(specifier):
                return True
        return False

    def check_build(self, sources: dict[str, str]) -> None:
        found = self.build_config()
        if not found:
            self.error("vite.config.ts", "no build config")
            return
        name, config = found
        if name.startswith("rollup"):
            self.warn(name, "built with Rollup; the fleet standard is Vite (see the starter template)")
        if "versionplaceholder" not in config:
            self.error(name, "never replaces versionplaceholder: the element would not carry its version")
        elif not re.search(r"versionplaceholder\s*:\s*[\w.]*version", config):
            self.warn(name, "versionplaceholder should be replaced with package.json's version")
        if name.startswith("vite") and f"src/{self.pkg}.ts" not in config:
            self.warn(name, f"the library entry should be src/{self.pkg}.ts")
        externals = self.externals(config)
        imported: dict[str, tuple[str, int]] = {}
        for file, code in sources.items():
            for match in re.finditer(
                r"""\b(?:import|export)\s+(type\s+)?(?:[^'";]*?\bfrom\s*)?['"]([^'"\n]+)['"]""", code
            ):
                if match.group(1):
                    continue
                specifier = match.group(2)
                if specifier.startswith((".", "/")) or specifier.startswith(("http:", "https:")):
                    continue
                imported.setdefault(specifier, (file, line_of(code, match.start())))
        declared = {
            **(self.package.get("dependencies") or {}),
            **(self.package.get("devDependencies") or {}),
            **(self.package.get("peerDependencies") or {}),
        }
        for specifier, (file, line) in sorted(imported.items()):
            package = package_of(specifier)
            external = self.is_external(specifier, externals)
            served = resolve_import_map(specifier, self.imports)
            if specifier == "echarts":
                self.warn(
                    file,
                    "imports bare 'echarts', which the import map does not provide; import values from "
                    "echarts/core, echarts/charts, … and write `import type` for types",
                    specifier,
                    line,
                )
                continue
            must = any(package == m.rstrip("/") or specifier.startswith(m) for m in MUST_BE_EXTERNAL)
            if must and not external:
                self.error(
                    file,
                    f"{package} is bundled; it must be external and come from Studio's import map "
                    "(it registers custom elements or relies on one shared instance)",
                    specifier,
                    line,
                )
            if external and served is None:
                # Type-only imports vanish in the build, so the built bundle (check_dist)
                # is where an unresolvable import is an error for certain.
                self.warn(
                    file,
                    f"{specifier} is external, but Studio's import map ({self.import_map_source}) does not "
                    "provide it: a value imported from it fails to load on cloud. Bundle it, or write "
                    "`import type` if only types come from it",
                    specifier,
                    line,
                )
            if external and served:
                declared_range = declared.get(package)
                if declared_range is None:
                    self.warn("package.json", f"{package} is imported from the host but not declared; add it to peerDependencies and devDependencies", package)
                elif major(str(declared_range)) and int(served.split(".")[0] or 0) not in major(str(declared_range)):
                    self.warn("package.json", f"{package} {declared_range} does not include the import map's version {served}", package)

    # -- source ------------------------------------------------------------

    def load_sources(self) -> dict[str, str]:
        sources = {}
        for path in sorted((self.repo / "src").rglob("*")):
            if path.suffix in (".ts", ".js", ".mjs") and not path.name.endswith(".d.ts") and path.is_file():
                rel = path.relative_to(self.repo).as_posix()
                sources[rel] = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        return sources

    def check_sources(self, sources: dict[str, str]) -> None:
        entry = f"src/{self.pkg}.ts"
        if entry not in sources:
            self.error(entry, "missing: the component's entry file")
        tag = f"{self.pkg}-versionplaceholder"
        registered = False
        for file, code in sources.items():
            for match in re.finditer(
                r"""(?:@customElement|customElements\.define)\(\s*['"`]([^'"`]+)['"`]""", code
            ):
                name, line = match.group(1), line_of(code, match.start())
                if name == tag:
                    registered = True
                elif re.search(r"-\d+\.\d+\.\d+$", name):
                    self.error(file, f"<{name}> hard-codes a version; register <{self.pkg}-versionplaceholder>", name, line)
                elif not name.endswith("-versionplaceholder"):
                    self.error(
                        file,
                        f"<{name}> is registered without the version suffix; a second version of this widget "
                        f"on the same page throws on define. Name it <{self.pkg}-…-versionplaceholder>",
                        name,
                        line,
                    )
            self.check_code(file, code)
        if sources and not registered:
            self.error(entry, f"no element <{tag}> is registered; Studio renders <{self.pkg}-<version>> and waits for it forever")
        code = sources.get(entry, "")
        if code and not re.search(r"@property\([^)]*\)\s*(?:(?:public|private|protected|declare|readonly)\s+)*inputData\b", code):
            self.error(entry, "declares no @property() inputData; Studio passes the config through it", "inputData")
        if code and not re.search(r"@property\([^)]*\)\s*(?:(?:public|private|protected|declare|readonly)\s+)*theme\b", code):
            self.warn(entry, "declares no @property() theme", "theme")

    PATTERNS: list[tuple[str, str, str, str]] = [
        # level, regex, path, message
        ("ERROR", r"this\.inputData(?:!?\??\.[A-Za-z_$][\w$]*|!?\[[^\]\n]*\])+\s*(?:=(?![=>])|\+=|-=|\?\?=|\|\|=|&&=)",
         "inputData", "writes into inputData, which belongs to the host and shares rows with other tiles; derive a copy"),
        ("ERROR", r"this\.inputData(?:!?\??\.[A-Za-z_$][\w$]*|!?\[[^\]\n]*\])*!?\??\.(?:sort|reverse|splice|push|pop|shift|unshift|fill|copyWithin)\(",
         "inputData", "mutates an array of inputData in place; sort or change a copy"),
        ("ERROR", r"\bdelete\s+this\.inputData\b", "inputData", "deletes from inputData, which belongs to the host"),
        ("ERROR", r"\blocation\.(?:href|hash|search|pathname)\s*=(?!=)|\blocation\.(?:assign|replace|reload)\(",
         "location", "navigates by itself; dispatch nav-submit or param-submit and let Studio navigate"),
        ("ERROR", r"\bhistory\.(?:pushState|replaceState|back|forward|go)\(",
         "history", "changes the browser history; dispatch nav-submit or param-submit instead"),
        ("ERROR", r"new\s+(?:WebSocket|EventSource)\(|\bautobahn\b|\bmqtt\b",
         "connection", "opens its own connection; data comes through inputData and actions go through events"),
        ("WARN", r"\b(?:localStorage|sessionStorage)\b", "storage", "uses browser storage; a widget's state belongs in its config"),
        ("WARN", r"\bfetch\(|\bXMLHttpRequest\b", "fetch", "fetches by itself; data reaches a widget through inputData (fetch only static assets)"),
        ("WARN", r"\bdocument\.(?:head|body)\.(?:append|appendChild|prepend|insertBefore)\(",
         "document", "changes the page outside the widget; keep everything in the shadow root"),
        ("WARN", r"\bwindow\.[A-Za-z_$][\w$]*\s*=(?!=)", "window", "sets a global; widgets of several versions share the page"),
        ("ERROR", r"\.getOption\(\)", "getOption",
         "ECharts getOption() fed back into setOption() nests the option one level per update until the stack overflows; build from structuredClone(template)"),
        ("WARN", r"\bthis\.[\w$]+\s*=\s*[^;\n]*getComputedStyle\(",
         "getComputedStyle", "caches a computed colour; it goes stale on the next board style edit. Use a var() chain, or resolve at the point of use"),
        ("WARN", r"var\(\s*--re-tile-background-color",
         "--re-tile-background-color", "paints the tile background, which Studio already paints; a translucent colour is applied twice"),
        ("WARN", r"--re-(?:primary|accent|hover|border)-color\b", "--re-*", "Studio never sets this custom property"),
        ("WARN", r"Date\.parse\([^)\n]*\btsp\b", "tsp",
         "Date.parse() on a timestamp: bound timestamps are epoch-millisecond numbers, which it turns into NaN"),
        ("WARN", r"\bconsole\.log\(", "console", "console.log left in"),
        ("WARN", r"\bunsafeHTML\(", "unsafeHTML", "renders config text as HTML; sanitise it, or say in CLAUDE.md why it is trusted"),
        ("WARN", r"\beval\(|\bnew\s+Function\(", "eval", "runs code built from strings"),
        ("WARN", r"<(?:div|span|li|h[1-6]|p)\b[^>]*@click=", "@click",
         "a clickable element that is not a control; use a <button> (or add a role, tabindex and key handling)"),
    ]  # fmt: skip

    def check_code(self, file: str, code: str) -> None:
        for level, regex, path, message in self.PATTERNS:
            for match in re.finditer(regex, code):
                self.add(level, file, message, path, line_of(code, match.start()))
        for match in re.finditer(r"""new\s+CustomEvent\(\s*['"`]([^'"`]+)['"`]""", code):
            if match.group(1) not in HOST_EVENTS:
                self.warn(file, f"Studio does not listen for {match.group(1)!r}; it only handles {', '.join(sorted(HOST_EVENTS))}", match.group(1), line_of(code, match.start()))
        for match in re.finditer(r"target=['\"]_blank['\"]", code):
            tag_start = code.rfind("<", 0, match.start())
            tag_end = code.find(">", match.end())
            if "rel=" not in code[tag_start : tag_end if tag_end != -1 else None]:
                self.warn(file, 'a link opening a new tab needs rel="noopener noreferrer"', "target", line_of(code, match.start()))
        for match in re.finditer(r"<iframe\b", code):
            tag_end = code.find(">", match.end())
            if "sandbox" not in code[match.start() : tag_end if tag_end != -1 else None]:
                self.warn(file, "an <iframe> without sandbox; restrict it unless the embedded page needs more", "iframe", line_of(code, match.start()))
        if "echarts.init(" in code and ".dispose(" not in code:
            self.error(file, "creates ECharts instances but never disposes them; they leak with the whole tile", "echarts")
        if re.search(r"from\s*['\"]echarts/core['\"]", code) and "echarts.use(" not in code and ".use(" not in code:
            self.warn(file, "imports echarts/core without echarts.use([...]); unregistered components are silently missing", "echarts")
        if "new ResizeObserver" in code:
            if ".disconnect(" not in code:
                self.warn(file, "a ResizeObserver that is never disconnected", "ResizeObserver")
            elif "connectedCallback" not in code.replace("disconnectedCallback", ""):
                self.warn(file, "disconnects its ResizeObserver but never observes again in connectedCallback; Studio moves tiles by detaching and re-attaching them", "ResizeObserver")
        if "setInterval(" in code and "clearInterval(" not in code:
            self.warn(file, "setInterval() without clearInterval(); clear it in disconnectedCallback", "setInterval")
        if re.search(r"\b(?:window|document)\.addEventListener\(", code) and "removeEventListener(" not in code:
            self.warn(file, "a window/document listener that is never removed", "addEventListener")
        if re.search(r"\b\d*\.?\d+cq(?:w|h|i|b|min|max)\b", code) and not re.search(r"(?<![\w-])container(?:-type)?\s*:", code):
            self.warn(file, "uses cq units but declares no container (container-type: size on :host); they resolve against the viewport", "cq")
        host = re.search(r":host\s*\{([^}]*)\}", code)
        if host and not re.search(r"\bdisplay\s*:", host.group(1)):
            self.warn(file, ":host sets no display; a custom element is inline, so Studio's 100% size has no effect. Use display: block", ":host", line_of(code, host.start()))

    # -- schema ------------------------------------------------------------

    def check_schema(self) -> None:
        file = "src/definition-schema.json"
        text = self.read(file)
        if text is None:
            self.error(file, "missing: Studio cannot add or edit the widget without it")
            return
        try:
            schema = json.loads(text)
        except json.JSONDecodeError as exc:
            self.error(file, f"not valid JSON: {exc}")
            return
        if not isinstance(schema, dict):
            self.error(file, "the root must be an object")
            return
        self.schema = schema
        for key in ("title", "description", "aiSelection", "type", "properties"):
            if key not in schema:
                level = "WARN" if key in ("aiSelection",) else "ERROR"
                self.add(level, file, f"the root needs {key}", key)
        for key in sorted(set(schema) - {"title", "description", "aiSelection", "layout", "type", "properties", "$schema", "$comment"}):
            self.warn(file, "unexpected root key", key)
        if schema.get("type") != "object":
            self.error(file, 'the root type must be "object"', "type")
        description = str(schema.get("description", ""))
        if "TODO" in description:
            self.error(file, "the widget description is still the template's TODO text", "description")
        first_two = " ".join(re.split(r"(?<=[.!?])\s+", " ".join(description.split()))[:2])
        if "e.g. " in first_two:
            self.warn(file, "'e.g. ' in the first two sentences: the widget catalog cuts sentences at '. '; write 'such as'", "description")
        self.check_ai_selection(file, schema.get("aiSelection"), description)
        self.check_layout(file, schema.get("layout"))
        props = schema.get("properties")
        if isinstance(props, dict):
            self.check_properties(file, props, [], [])
        size = len(json.dumps({"package_name": self.pkg, "version": self.version, "definition_schema": schema, "default_config": self.defaults}, indent=2, ensure_ascii=True))
        if size > AI_SCHEMA_BUDGET:
            self.warn(file, f"schema and default config are {size:,} characters; above {AI_SCHEMA_BUDGET:,} the AI only gets an overview of the top-level settings")

    def check_layout(self, file: str, layout: Any) -> None:
        """`layout` declares a natural tile size the platform keeps fixed:
        {fixedHeight: true, height: <px>} and/or {fixedWidth: true, width: <px>}."""
        if layout is None:
            return
        if not isinstance(layout, dict):
            self.error(file, "layout must be an object such as {fixedHeight: true, height: 48}", "layout")
            return
        for key in sorted(set(layout) - {"fixedWidth", "width", "fixedHeight", "height"}):
            self.warn(file, "layout only has fixedWidth, width, fixedHeight and height", f"layout.{key}")
        axes = bad = 0
        for flag, size in (("fixedHeight", "height"), ("fixedWidth", "width")):
            if flag not in layout and size not in layout:
                continue
            value = layout.get(size)
            if layout.get(flag) is not True:
                bad += 1
                self.error(file, f"{size} only counts together with {flag}: true; leave both out for a free {size}", f"layout.{flag}")
            elif not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                bad += 1
                self.error(file, f"{size} must be the tile's natural {size} in pixels, a positive number", f"layout.{size}")
            else:
                axes += 1
        if not axes and not bad:
            self.warn(file, "layout fixes neither height nor width; remove it", "layout")

    def check_ai_selection(self, file: str, selection: Any, description: str) -> None:
        if selection is None:
            return
        if not isinstance(selection, dict):
            self.error(file, "aiSelection must be an object with dataShape, useWhen and notFor", "aiSelection")
            return
        for key in sorted(set(selection) - {"dataShape", "useWhen", "notFor"}):
            self.warn(file, "aiSelection only has dataShape, useWhen and notFor", f"aiSelection.{key}")
        shape = selection.get("dataShape")
        if not isinstance(shape, str) or not shape.strip():
            self.error(file, "dataShape must be a non-empty string (the catalog generator splits it as text)", "aiSelection.dataShape")
        elif "TODO" in shape:
            self.error(file, "still the template's TODO text", "aiSelection.dataShape")
        for key in ("useWhen", "notFor"):
            entries = selection.get(key)
            if not isinstance(entries, list) or not entries or not all(isinstance(e, str) for e in entries):
                self.error(file, f"{key} must be a non-empty list of strings", f"aiSelection.{key}")
                continue
            for i, entry in enumerate(entries):
                if "TODO" in entry:
                    self.error(file, "still the template's TODO text", f"aiSelection.{key}.{i}")
                if key == "notFor":
                    named = set(re.findall(r"widget-[a-z0-9-]*[a-z0-9]", entry))
                    if not named:
                        self.warn(file, "names no widget to use instead; every notFor entry should route somewhere", f"aiSelection.notFor.{i}")
                    for widget in sorted(named - KNOWN_WIDGETS - {self.pkg}):
                        self.warn(file, f"{widget} is not a widget the platform registers", f"aiSelection.notFor.{i}")
        routing = len(description) + len(json.dumps(selection, ensure_ascii=False))
        if routing > AI_ROUTING_BUDGET:
            self.warn(file, f"description and aiSelection are {routing:,} characters; all widgets share one prompt budget that is nearly full, so aim for under 2,000", "aiSelection")

    def check_properties(self, file: str, props: dict, spath: list[str], cpath: list[str]) -> None:
        orders: dict[float, str] = {}
        for key, node in props.items():
            path = ".".join([*spath, key])
            if not isinstance(node, dict):
                self.error(file, "a property must be an object", path)
                continue
            for required in ("title", "description", "type"):
                if not node.get(required):
                    self.error(file, f"needs a {required}" + (" (the editor's label and the generated type name)" if required == "title" else " (shown in the editor and read by the AI)" if required == "description" else ""), path)
            order = node.get("order")
            if order is None:
                self.warn(file, "needs an order; Studio shows properties without one first, widget.py last", path)
            elif isinstance(order, (int, float)) and not isinstance(order, bool):
                if order in orders and "condition" not in node and "condition" not in props.get(orders[order], {}):
                    self.warn(file, f"same order ({order}) as {orders[order]!r}; siblings show in an undefined order", path)
                orders.setdefault(order, key)
            self.check_property(file, key, node, path, [*cpath, key])

    def check_property(self, file: str, key: str, node: dict, path: str, cpath: list[str]) -> None:
        kind = node.get("type")
        for unknown in sorted(set(node) - PROPERTY_KEYS):
            if unknown in UNRENDERABLE:
                self.error(file, f"{unknown}: Studio's editor cannot render schema composition or references", path)
            elif unknown == "color":
                self.warn(file, "color: true is read by nothing; type: color is enough", path)
            elif unknown == "required":
                self.warn(file, 'property-level "required" is ignored by Studio, the AI and json2ts; say it in the description and handle a missing value in code', path)
            elif unknown in INERT:
                self.warn(file, f"{unknown}: {INERT[unknown]}", path)
            elif unknown != "aiSelection":
                close = difflib.get_close_matches(unknown, sorted(PROPERTY_KEYS), n=1)
                hint = f"; did you mean {close[0]!r}?" if close else ""
                self.warn(file, f"unknown keyword {unknown!r}{hint}", path)
        if isinstance(kind, list):
            self.error(file, "type must be one string; Studio compares it with ===", path)
            return
        if kind in BAD_TYPES:
            level, message = BAD_TYPES[kind]
            self.add(level, file, f"type {kind!r}: {message}", path)
        elif kind not in SCHEMA_TYPES and kind is not None:
            self.error(file, f"unknown type {kind!r}; use one of {', '.join(sorted(SCHEMA_TYPES))}", path)
        if node.get("dataDrivenDisabled") is False:
            self.warn(file, "dataDrivenDisabled: false is the same as leaving it out; leave it out", path)
        if kind in ("actionApp", "targetColumn") and node.get("dataDrivenDisabled") is not True:
            self.warn(file, f"a {kind} property needs dataDrivenDisabled: true, or the editor opens the binding picker instead of its own", path)
        if "contentMediaType" in node:
            media = node["contentMediaType"]
            if kind != "textarea":
                self.warn(file, "contentMediaType does something only on a textarea: the language its text dialog highlights", path)
            elif not isinstance(media, str) or media not in HIGHLIGHTED_MEDIA_TYPES:
                self.warn(file, f"contentMediaType {media!r}: Studio highlights only {', '.join(sorted(HIGHLIGHTED_MEDIA_TYPES))}; others get the plain text dialog", path)
        if "enum" in node:
            if not isinstance(node["enum"], list) or not node["enum"]:
                self.error(file, "enum must be a non-empty list", path)
            elif kind != "string":
                self.warn(file, "Studio shows a select only for string enums", path)
        if "enumLabels" in node:
            labels = node["enumLabels"]
            if not isinstance(labels, list):
                self.warn(file, "enumLabels must be a list in the order of enum; Studio looks labels up by position", path)
            elif isinstance(node.get("enum"), list) and len(labels) != len(node["enum"]):
                self.warn(file, f"enumLabels has {len(labels)} labels for {len(node['enum'])} enum values", path)
        if "condition" in node:
            self.check_condition(file, node["condition"], path, cpath)
        if kind == "object" and isinstance(node.get("properties"), dict):
            self.check_properties(file, node["properties"], path.split("."), cpath)
        if kind == "array":
            items = node.get("items")
            if not isinstance(items, dict):
                self.error(file, "an array needs items: one schema for every element", path)
            else:
                item_type = items.get("type")
                if item_type == "object" and isinstance(items.get("properties"), dict):
                    self.check_properties(file, items["properties"], [*path.split("."), "[]"], [*cpath, "[]"])
                elif item_type == "array" and isinstance(items.get("items"), dict):
                    inner = items["items"]
                    if inner.get("type") == "object" and isinstance(inner.get("properties"), dict):
                        self.check_properties(file, inner["properties"], [*path.split("."), "[]", "[]"], [*cpath, "[]", "[]"])

    def check_condition(self, file: str, condition: Any, path: str, cpath: list[str]) -> None:
        if not isinstance(condition, dict):
            self.error(file, "condition must be {relativePath, showIfValueIn}", path)
            return
        relative = condition.get("relativePath")
        values = condition.get("showIfValueIn")
        if not isinstance(relative, str) or not relative.startswith(".."):
            self.error(file, "condition.relativePath must be a relative path starting with '..'", path)
            return
        if not isinstance(values, list) or not values:
            self.error(file, "condition.showIfValueIn must be a non-empty list", path)
            return
        target_path = relative_target(cpath, relative)
        target = find_node(self.schema or {}, target_path) if target_path is not None else None
        if target is None:
            self.error(file, f"condition points at {relative!r}, which resolves to no property", path)
            return
        if target.get("dataDrivenDisabled") is not True:
            self.warn(file, "the condition's target can be bound to data; a bound value never matches, so mark the target dataDrivenDisabled", path)
        ttype = target.get("type")
        if ttype == "boolean":
            for value in values:
                if not isinstance(value, bool):
                    self.error(file, f"{value!r} never matches a boolean target (compared with ===)", path)
        elif ttype == "string" and isinstance(target.get("enum"), list):
            for value in values:
                if value not in target["enum"]:
                    self.error(file, f"{value!r} is not one of the target's enum values", path)
        else:
            self.warn(file, "a condition's target should be a boolean or a string enum", path)
        for value in values:
            if isinstance(value, str) and ":" in value:
                self.warn(file, f"{value!r} contains ':', which the editor's value decoding cuts off", path)
        # A target in the same item of a bindable array reads as unset once the array is bound.
        if "[]" in target_path:
            last = len(target_path) - 1 - target_path[::-1].index("[]")
            if target_path[: last + 1] == cpath[: last + 1]:
                array = find_node(self.schema or {}, target_path[:last])
                if array is not None and array.get("dataDrivenDisabled") is not True:
                    self.warn(file, "the condition reads a sibling inside a bindable array; once the array is bound to a table the field is always hidden", path)

    # -- default config ----------------------------------------------------

    def load_defaults(self) -> None:
        file = "src/default-data.json"
        text = self.read(file)
        if text is None:
            self.error(file, "missing: Studio cannot add the widget to a board without it")
            return
        try:
            self.defaults = json.loads(text)
        except json.JSONDecodeError as exc:
            self.error(file, f"not valid JSON: {exc}")

    def check_defaults(self) -> None:
        if self.defaults is None or not isinstance(self.schema, dict):
            return
        file = "src/default-data.json"
        if not isinstance(self.defaults, dict):
            self.error(file, "the default config must be an object")
            return
        self.check_value(file, self.defaults, self.schema, [], self.defaults)

    def check_value(self, file: str, value: Any, node: dict, cpath: list[str], root: Any) -> None:
        path = ".".join(str(p) for p in cpath) or "-"
        if isinstance(value, dict) and ({"tableRef", "valueRef"} & set(value)):
            self.error(file, "holds a data binding; the default config is plain values (Studio and the demo render it raw)", path)
            return
        if value is None:
            self.warn(file, "null; leave the key out instead", path)
            return
        kind = node.get("type")
        if isinstance(value, str) and re.search(r"\$(?:str|num|bool):", value):
            self.error(file, "holds a $str:/$num:/$bool: prefix; write plain values (Studio adds the prefixes on drop)", path)
        expected = {
            "string": (str,), "color": (str,), "textarea": (str,), "image": (str,),
            "number": (int, float), "boolean": (bool,), "object": (dict,), "array": (list,),
            "targetColumn": (str, dict), "actionApp": (int, str), "actionDevice": (int, str), "font": (dict, str),
        }.get(kind)  # fmt: skip
        if expected and (not isinstance(value, expected) or (kind == "number" and isinstance(value, bool))):
            self.error(file, f"{type(value).__name__} where the schema says {kind}", path)
            return
        if kind in ("actionApp", "actionDevice", "targetColumn"):
            self.warn(file, f"{kind} only exists in a running project; leave it out of the default config", path)
        if isinstance(node.get("enum"), list) and value not in node["enum"]:
            self.error(file, f"{value!r} is not one of {node['enum']}", path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(node.get("minimum"), (int, float)) and value < node["minimum"]:
                self.error(file, f"{value} is below the minimum {node['minimum']}", path)
            if isinstance(node.get("maximum"), (int, float)) and value > node["maximum"]:
                self.error(file, f"{value} is above the maximum {node['maximum']}", path)
        if isinstance(value, dict) and kind == "object":
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            for key, child in value.items():
                child_path = [*cpath, key]
                where = ".".join(str(p) for p in child_path)
                if key not in props:
                    self.error(file, "not declared in the schema: the editor never shows it, the AI rejects it, and inside an object Studio strips it", where)
                    continue
                self.check_value(file, child, props[key], child_path, root)
                condition = props[key].get("condition")
                if isinstance(condition, dict) and isinstance(condition.get("relativePath"), str):
                    target = relative_target([str(p) for p in child_path], condition["relativePath"])
                    actual = self.lookup(root, target) if target is not None else None
                    shown = condition.get("showIfValueIn") or []
                    # Studio's editor reads an unset target as false.
                    if not strictly_in(False if actual is None else actual, shown):
                        self.warn(file, f"set although its condition ({condition['relativePath']} in {shown}) is not met; the editor deletes it and the AI rejects it", where)
        if isinstance(value, list) and kind == "array" and isinstance(node.get("items"), dict):
            for i, item in enumerate(value):
                self.check_value(file, item, node["items"], [*cpath, i], root)

    @staticmethod
    def lookup(root: Any, path: list[str]) -> Any:
        node = root
        for part in path:
            if isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            elif isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    # -- generated types -----------------------------------------------------

    def check_types(self) -> None:
        file = "src/definition-schema.d.ts"
        text = self.read(file)
        if text is None:
            self.error(file, "missing; run npm run types")
            return
        title = str((self.schema or {}).get("title", ""))
        if title and f"interface {type_name(title)} " not in text:
            self.error(file, f"does not export {type_name(title)}, the type of the schema's title; run npm run types")
        json2ts = self.repo / "node_modules" / ".bin" / "json2ts"
        node = find_node_binary()
        if not (json2ts.exists() and node and (self.repo / "src/definition-schema.json").is_file()):
            return
        flags = re.findall(r"--[\w.-]+(?:=\S+)?", str((self.package.get("scripts") or {}).get("types", "")))
        try:
            done = subprocess.run(
                [node, str(json2ts), *flags],
                input=(self.repo / "src/definition-schema.json").read_text(encoding="utf-8"),
                capture_output=True,
                text=True,
                cwd=self.repo,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return
        if done.returncode == 0 and done.stdout and done.stdout != text:
            self.error(file, "out of date with src/definition-schema.json; run npm run types (the release refuses stale types)")

    def run_typecheck(self) -> None:
        tsc = self.repo / "node_modules" / ".bin" / "tsc"
        node = find_node_binary()
        if not tsc.exists() or not node:
            self.warn("tsconfig.json", "--typecheck needs node and the repo's node_modules (npm install)")
            return
        scripts = self.package.get("scripts") or {}
        if "typecheck" in scripts:
            command = [node, str(tsc), "-p", ".", "--noEmit"]
        else:
            command = [
                node, str(tsc), "--noEmit", "--incremental", "false", "--skipLibCheck", "--strict",
                "--experimentalDecorators", "--useDefineForClassFields", "false", "--target", "es2021",
                "--lib", "es2021,dom,dom.iterable", "--module", "esnext", "--moduleResolution", "bundler",
                "--resolveJsonModule", f"src/{self.pkg}.ts",
            ]  # fmt: skip
        done = subprocess.run(command, capture_output=True, text=True, cwd=self.repo, timeout=600)
        for line in done.stdout.splitlines():
            match = re.match(r"^(.+?)\((\d+),\d+\): error (TS\d+): (.*)$", line)
            if match and "node_modules" not in match.group(1):
                self.error(match.group(1), match.group(4), match.group(3), int(match.group(2)))

    # -- thumbnails, docs, dist ----------------------------------------------

    def check_thumbnails(self) -> None:
        # widget-scada's palette entries are its symbols; its package thumbnail is not shown.
        if self.pkg == "widget-scada":
            return
        present = []
        for name, fmt in (("thumbnail.webp", "webp"), ("thumbnail.png", "png")):
            path = self.repo / name
            if not path.is_file():
                continue
            present.append(path)
            size = image_size(path)
            if size is None or size[0] != fmt:
                self.error(name, f"is not a {fmt} image")
                continue
            _, width, height = size
            if height and abs(width / height - 4 / 3) > 0.08:
                self.warn(name, f"{width}×{height} is not 4:3; the palette shows thumbnails at 4:3")
            if fmt == "webp" and width > 800:
                self.warn(name, f"{width} px wide; the palette shows it at most 200 px wide, 400×300 is enough")
        if not present:
            self.error("thumbnail.webp", "no thumbnail.webp or thumbnail.png; the palette shows the widget with it")
            return
        if len(present) == 1:
            self.warn(present[0].name, "only one of thumbnail.webp and thumbnail.png exists; ship both")
        siblings = [
            p
            for p in self.context.parent.glob("widget-*")
            if p.is_dir() and p.resolve() != self.context and p.name != "widget-scada"
        ]
        for path in present:
            digest = hashlib.md5(path.read_bytes()).hexdigest()
            for sibling in siblings:
                other = sibling / path.name
                if other.is_file() and hashlib.md5(other.read_bytes()).hexdigest() == digest:
                    self.warn(path.name, f"is identical to {sibling.name}'s thumbnail; show this widget")

    def check_docs(self) -> None:
        for name in ("CLAUDE.md", "README.md"):
            text = self.read(name)
            if text is None:
                self.warn(name, "missing")
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"\bTODO\b", line):
                    self.error(name, "template text left in: " + line.strip()[:80], "TODO", i)
                if re.search(r"RESWARM/frontend|IronFlock-UI|@record-evolution/", line):
                    self.warn(name, "refers to a retired name (RESWARM/frontend, IronFlock-UI or @record-evolution)", "-", i)
                if name == "README.md":
                    for tag in re.findall(rf"\b{re.escape(self.pkg)}-(\d+\.\d+\.\d+)\b", line):
                        self.warn(name, f"hard-codes the tag {self.pkg}-{tag}; tell readers to build it from the installed version", "-", i)
        if "TODO" in str(self.package.get("description", "")):
            self.error("package.json", "the description is still the template's TODO text", "description")

    def check_dist(self) -> None:
        bundle = self.repo / "dist" / f"{self.pkg}.js"
        if not bundle.is_file():
            return
        file = bundle.relative_to(self.repo).as_posix()
        code = bundle.read_text(encoding="utf-8", errors="replace")
        if "versionplaceholder" in code:
            self.error(file, "still contains versionplaceholder; the replace plugin did not run")
        tags = set(re.findall(rf"""["']{re.escape(self.pkg)}-(\d+\.\d+\.\d+)["']""", code))
        if tags and self.version not in tags:
            self.warn(file, f"registers {', '.join(sorted(tags))} but package.json is {self.version}; Studio's dev server serves this file, so rebuild (npm run build)")
        for match in re.finditer(r"""^\s*(?:import|export)\b[^'"\n]*?(?:from\s*)?["']([^"'\n]+)["']""", code, re.M):
            specifier = match.group(1)
            if specifier.startswith((".", "/", "http:", "https:", "data:")):
                if specifier.startswith("."):
                    self.error(file, f"imports {specifier}; the bundle must be one file, because the CDN URL it is loaded from is not its folder", specifier, line_of(code, match.start()))
                continue
            if resolve_import_map(specifier, self.imports) is None:
                self.error(file, f"imports {specifier!r}, which Studio's import map does not provide; it fails to load on cloud", specifier, line_of(code, match.start()))

    # -- run -----------------------------------------------------------------

    def run(self) -> list[Finding]:
        if not self.check_package():
            return self.findings
        sources = self.load_sources()
        self.check_build(sources)
        self.check_sources(sources)
        self.load_defaults()
        self.check_schema()
        self.check_defaults()
        self.check_types()
        if self.typecheck:
            self.run_typecheck()
        self.check_thumbnails()
        self.check_docs()
        self.check_dist()
        return self.findings


def committed_findings(repo: Path, revision: str, typecheck: bool) -> list[Finding] | None:
    """The findings of the repo as committed at `revision`, checked in a
    temporary copy made with `git archive` (which changes nothing in the repo).
    The copy borrows the repo's node_modules, so the generated-types check and
    --typecheck run on both sides and older type errors are not reported as new."""
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", revision], capture_output=True)
    if archive.returncode != 0:
        print(
            f"note: cannot read {revision} ({archive.stderr.decode().strip() or 'git archive failed'}), "
            "for example in a repository without commits; showing every finding."
        )
        return None
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / repo.resolve().name
        copy.mkdir()
        subprocess.run(["tar", "-x", "-C", str(copy)], input=archive.stdout, check=True)
        modules = repo / "node_modules"
        if modules.is_dir():
            (copy / "node_modules").symlink_to(modules.resolve(), target_is_directory=True)
        return WidgetCheck(copy, typecheck, context=repo).run()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", nargs="?", default=".", help="the widget repository (default: .)")
    parser.add_argument("--typecheck", action="store_true", help="also type-check src/ with the repo's tsc")
    parser.add_argument("--since", metavar="REV", help="only report findings the git revision REV (e.g. HEAD) did not have")
    args = parser.parse_args()
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"error: {repo} is not a folder", file=sys.stderr)
        return 2
    check = WidgetCheck(repo, args.typecheck)
    findings = check.run()
    before = committed_findings(repo, args.since, args.typecheck) if args.since else None
    if before is not None:
        # Line numbers move with every edit, so match findings without them.
        seen = Counter((f.level, f.file, f.path, f.message) for f in before)
        new = []
        for f in findings:
            key = (f.level, f.file, f.path, f.message)
            if seen[key]:
                seen[key] -= 1
            else:
                new.append(f)
        print(f"{len(findings) - len(new)} finding(s) were already there at {args.since}; showing the new ones.\n")
        findings = new
    order = {"ERROR": 0, "WARN": 1}
    for f in sorted(findings, key=lambda f: (f.file, f.line or 0, order[f.level])):
        where = f"{f.file}:{f.line}" if f.line else f.file
        print(f"{f.level:5} {where} {f.path}: {f.message}")
    errors = sum(f.level == "ERROR" for f in findings)
    warnings = len(findings) - errors
    print(f"\n{errors} error(s), {warnings} warning(s) in {repo.resolve().name}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
