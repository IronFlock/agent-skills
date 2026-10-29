#!/usr/bin/env python3
"""Regression tests for the ironflock-widgets skill's scripts.

    python3 tests/widget_checks.py

1. new_widget.py scaffolds tests' widget-sample from the starter template, and
   refuses bad names and non-empty folders.
2. The scaffold, as generated, reports exactly its TODO texts and the missing
   thumbnails.
3. The scaffold with those written (a "finished" widget) produces no findings
   at all.
4. Every mutation below plants one known mistake in a fresh finished copy, and
   check_widget.py must report it: the expected level, file, path and part of
   the message. Each mutation is a negative control for one check.
5. Every accepted shape below is correct, and check_widget.py must report
   nothing for it: a positive control for a check that once misfired.

Offline and without node: the json2ts and --typecheck comparisons need a
node_modules and are exercised by hand (see README).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT.parent / "plugins/ironflock/skills/ironflock-widgets/scripts"
NEW_WIDGET = SCRIPTS / "new_widget.py"
CHECK = SCRIPTS / "check_widget.py"
FIXTURES = ROOT / "widgets"
FINDING = re.compile(r"^(ERROR|WARN)\s+(\S+) (\S+): (.*)$")


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", *args], capture_output=True, text=True, cwd=cwd)


def findings(repo: Path) -> list[tuple[str, str, str, str]]:
    done = run(str(CHECK), str(repo))
    if done.returncode not in (0, 1):
        sys.exit(f"check_widget.py crashed on {repo.name}:\n{done.stdout}{done.stderr}")
    return [(m[1], m[2], m[3], m[4]) for m in map(FINDING.match, done.stdout.splitlines()) if m]


def edit(repo: Path, relative: str, change: Callable[[str], str]) -> None:
    path = repo / relative
    path.write_text(change(path.read_text()))


def edit_json(repo: Path, relative: str, change: Callable[[dict], None]) -> None:
    path = repo / relative
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data, indent=4) + "\n")


def finish(repo: Path) -> None:
    """Write what a developer writes after scaffolding: the TODO texts, the
    thumbnails and a lockfile."""

    def schema(s: dict) -> None:
        s["description"] = "Shows the latest value of each series as a large number. Use it for KPI tiles."
        s["aiSelection"] = {
            "dataShape": "One number per series, newest row last; a pivot column splits a series.",
            "useWhen": ["A current figure is the whole point (dataseries[].data[].value)."],
            "notFor": ["How the value changes over time — use widget-linechart."],
        }

    edit_json(repo, "src/definition-schema.json", schema)
    edit_json(repo, "package.json", lambda p: p.update(description="IronFlock board widget: sample readouts"))
    edit(repo, "README.md", lambda t: re.sub(r"TODO:[^\n]*\n[^\n]*\n", "Shows readouts.\n", t, count=1))
    edit(repo, "CLAUDE.md", lambda t: re.sub(r"TODO:[^\n]*\n", "", t))
    for name in ("thumbnail.png", "thumbnail.webp"):
        shutil.copy(FIXTURES / name, repo / name)
    package = json.loads((repo / "package.json").read_text())
    (repo / "package-lock.json").write_text(
        json.dumps({"name": package["name"], "version": package["version"], "lockfileVersion": 3}) + "\n"
    )


ENTRY = "src/widget-sample.ts"
SCHEMA = "src/definition-schema.json"
DEFAULTS = "src/default-data.json"


def series_item(s: dict) -> dict:
    return s["properties"]["dataseries"]["items"]["properties"]


def with_style_condition(s: dict, shown_for: list) -> None:
    """Give each series a literal Style enum and show its unit only for the
    listed styles."""
    series_item(s).update(
        style={
            "title": "Style",
            "description": "How the value is drawn.",
            "type": "string",
            "enum": ["plain", "boxed"],
            "dataDrivenDisabled": True,
            "order": 6,
        }
    )
    series_item(s)["unit"].update(condition={"relativePath": "../style", "showIfValueIn": shown_for})


def add_code(code: str) -> Callable[[str], str]:
    """Insert code into the component class, right after `version`."""
    return lambda t: t.replace("version: string = 'versionplaceholder'\n", "version: string = 'versionplaceholder'\n" + code + "\n", 1)


# name: (mutation, [(level, file, path, part of the message)])
Mutation = Callable[[Path], None]
MUTATIONS: dict[str, tuple[Mutation, list[tuple[str, str, str, str]]]] = {
    # -- identity and package ----------------------------------------------
    "unversioned child element": (
        lambda r: edit(r, ENTRY, lambda t: t + "\n@customElement('sample-helper')\nexport class Helper extends LitElement {}\n"),
        [("ERROR", ENTRY, "sample-helper", "without the version suffix")],
    ),
    "hard-coded version in the tag": (
        lambda r: edit(r, ENTRY, lambda t: t.replace("'widget-sample-versionplaceholder'", "'widget-sample-1.0.0'")),
        [("ERROR", ENTRY, "widget-sample-1.0.0", "hard-codes a version"), ("ERROR", ENTRY, "-", "no element <widget-sample-versionplaceholder>")],
    ),
    "no version replacement in the build": (
        lambda r: edit(r, "vite.config.ts", lambda t: t.replace("replace({ versionplaceholder: pkg.version, preventAssignment: true })", "")),
        [("ERROR", "vite.config.ts", "-", "never replaces versionplaceholder")],
    ),
    "main points elsewhere": (
        lambda r: edit_json(r, "package.json", lambda p: p.update(main="src/widget-sample.ts")),
        [("ERROR", "package.json", "main", "the CDN serves it")],
    ),
    "src not published": (
        lambda r: edit_json(r, "package.json", lambda p: p.update(files=["dist", "thumbnail.png", "thumbnail.webp"])),
        [("ERROR", "package.json", "files", '"src"')],
    ),
    "old npm-version release hook": (
        lambda r: edit_json(r, "package.json", lambda p: p["scripts"].update(postversion="git push --follow-tags")),
        [("ERROR", "package.json", "scripts.postversion", "npm version")],
    ),
    "no release recipe": (
        lambda r: edit(r, "Justfile", lambda t: t.replace("release-patch:", "release-later:")),
        [("WARN", "Justfile", "release-patch", "release-patch recipe")],
    ),
    "no security workflow": (
        lambda r: (r / ".github/workflows/security.yml").unlink(),
        [("WARN", ".github/workflows/security.yml", "-", "security checks")],
    ),
    "no OIDC permission": (
        lambda r: edit(r, ".github/workflows/build-publish.yml", lambda t: t.replace("id-token: write", "")),
        [("ERROR", ".github/workflows/build-publish.yml", "-", "id-token: write")],
    ),
    "stale link scripts": (
        lambda r: edit_json(r, "package.json", lambda p: p["scripts"].update(link="npm link && cd ../RESWARM/frontend && npm link x")),
        [("WARN", "package.json", "scripts.link", "RESWARM/frontend")],
    ),
    # -- build and libraries -------------------------------------------------
    "bundled Material Web": (
        lambda r: edit(r, ENTRY, lambda t: "import '@material/web/icon/icon.js'\n" + t),
        [("ERROR", ENTRY, "@material/web/icon/icon.js", "must be external")],
    ),
    "external the host does not provide": (
        lambda r: (
            edit(r, ENTRY, lambda t: "import { debounce } from 'lodash-es'\n" + t),
            edit(r, "vite.config.ts", lambda t: t.replace("external: [/^lit/, /^@lit/]", "external: [/^lit/, /^@lit/, 'lodash-es']")),
        ),
        [("WARN", ENTRY, "lodash-es", "does not provide it")],
    ),
    "a // inside an externals regex": (
        lambda r: (
            edit(r, ENTRY, lambda t: "import { debounce } from 'lodash-es'\n" + t),
            edit(r, "vite.config.ts", lambda t: t.replace("external: [/^lit/, /^@lit/]", "external: [/^lit/, /^@lit\\//, 'lodash-es']")),
        ),
        [("WARN", ENTRY, "lodash-es", "does not provide it")],
    ),
    "bare echarts import": (
        lambda r: edit(r, ENTRY, lambda t: "import { EChartsOption } from 'echarts'\n" + t),
        [("WARN", ENTRY, "echarts", "import type")],
    ),
    # -- source --------------------------------------------------------------
    "writes into inputData": (
        lambda r: edit(r, ENTRY, add_code("    reset() { this.inputData!.title = 'x' }")),
        [("ERROR", ENTRY, "inputData", "writes into inputData")],
    ),
    "sorts inputData in place": (
        lambda r: edit(r, ENTRY, add_code("    order() { this.inputData?.dataseries?.sort() }")),
        [("ERROR", ENTRY, "inputData", "mutates an array")],
    ),
    "navigates by itself": (
        lambda r: edit(r, ENTRY, add_code("    go() { window.location.href = '/x' }")),
        [("ERROR", ENTRY, "location", "nav-submit")],
    ),
    "ECharts getOption round trip": (
        lambda r: edit(r, ENTRY, add_code("    redraw(chart: any) { chart.setOption({ ...chart.getOption() }) }")),
        [("ERROR", ENTRY, "getOption", "structuredClone")],
    ),
    "ECharts never disposed": (
        lambda r: edit(r, ENTRY, add_code("    draw(echarts: any, div: any) { return echarts.init(div) }")),
        [("ERROR", ENTRY, "echarts", "never disposes")],
    ),
    "Date.parse on a timestamp": (
        lambda r: edit(r, ENTRY, add_code("    age(row: any) { return Date.now() - Date.parse(row.tsp) }")),
        [("WARN", ENTRY, "tsp", "epoch-millisecond")],
    ),
    "cached computed colour": (
        lambda r: edit(r, ENTRY, add_code("    color?: string\n    remember() { this.color = getComputedStyle(this).getPropertyValue('--re-text-color') }")),
        [("WARN", ENTRY, "getComputedStyle", "var() chain")],
    ),
    "paints the tile background": (
        lambda r: edit(r, ENTRY, lambda t: t.replace("container-type: size;", "container-type: size;\n            background: var(--re-tile-background-color);")),
        [("WARN", ENTRY, "--re-tile-background-color", "already paints")],
    ),
    "cq units without a container": (
        lambda r: edit(r, ENTRY, lambda t: t.replace("container-type: size;", "")),
        [("WARN", ENTRY, "cq", "declares no container")],
    ),
    "host without display": (
        lambda r: edit(r, ENTRY, lambda t: t.replace("display: block;\n            box-sizing", "box-sizing", 1)),
        [("WARN", ENTRY, ":host", "display: block")],
    ),
    "an event the host ignores": (
        lambda r: edit(r, ENTRY, add_code("    pick() { this.dispatchEvent(new CustomEvent('sample-picked')) }")),
        [("WARN", ENTRY, "sample-picked", "does not listen")],
    ),
    "clickable div": (
        lambda r: edit(r, ENTRY, lambda t: t.replace('<div class="readout">', '<div class="readout" @click=${() => this.requestUpdate()}>')),
        [("WARN", ENTRY, "@click", "<button>")],
    ),
    # -- schema --------------------------------------------------------------
    "property without a title": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["properties"]["title"].pop("title")),
        [("ERROR", SCHEMA, "title", "needs a title")],
    ),
    "type list": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["properties"]["subTitle"].update(type=["string", "number"])),
        [("ERROR", SCHEMA, "subTitle", "one string")],
    ),
    "unknown type": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["properties"]["subTitle"].update(type="text")),
        [("ERROR", SCHEMA, "subTitle", "unknown type")],
    ),
    "integer type": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["precision"].update(type="integer")),
        [("WARN", SCHEMA, "dataseries.[].precision", "integer")],
    ),
    "dead min keyword": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["precision"].update(min=0)),
        [("WARN", SCHEMA, "dataseries.[].precision", "use minimum")],
    ),
    "property-level required": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["label"].update(required=True)),
        [("WARN", SCHEMA, "dataseries.[].label", "required")],
    ),
    "keyword typo": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["unit"].update(dataDrivenDisable=True)),
        [("WARN", SCHEMA, "dataseries.[].unit", "did you mean 'dataDrivenDisabled'")],
    ),
    "media type on a plain string": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["label"].update(contentMediaType="text/markdown")),
        [("WARN", SCHEMA, "dataseries.[].label", "only on a textarea")],
    ),
    "media type Studio does not highlight": (
        lambda r: edit_json(
            r,
            SCHEMA,
            lambda s: s["properties"].update(
                notes={"title": "Notes", "description": "Text below the readouts.", "type": "textarea", "contentMediaType": "text/html", "order": 4}
            ),
        ),
        [("WARN", SCHEMA, "notes", "highlights only text/markdown")],
    ),
    "duplicate order": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["properties"]["subTitle"].update(order=1)),
        [("WARN", SCHEMA, "subTitle", "same order")],
    ),
    "array without items": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["data"].pop("items")),
        [("ERROR", SCHEMA, "dataseries.[].data", "needs items")],
    ),
    "condition to nowhere": (
        lambda r: edit_json(r, SCHEMA, lambda s: series_item(s)["unit"].update(condition={"relativePath": "../showUnit", "showIfValueIn": [True]})),
        [("ERROR", SCHEMA, "dataseries.[].unit", "resolves to no property")],
    ),
    "condition that never matches": (
        lambda r: edit_json(
            r,
            SCHEMA,
            lambda s: (
                series_item(s).update(showUnit={"title": "Show Unit", "description": "Show the unit.", "type": "boolean", "dataDrivenDisabled": True, "order": 6}),
                series_item(s)["unit"].update(condition={"relativePath": "../showUnit", "showIfValueIn": ["true"]}),
            ),
        ),
        [("ERROR", SCHEMA, "dataseries.[].unit", "never matches a boolean")],
    ),
    "condition on a bindable target": (
        lambda r: edit_json(
            r,
            SCHEMA,
            lambda s: (
                series_item(s).update(showUnit={"title": "Show Unit", "description": "Show the unit.", "type": "boolean", "order": 6}),
                series_item(s)["unit"].update(condition={"relativePath": "../showUnit", "showIfValueIn": [True]}),
            ),
        ),
        [("WARN", SCHEMA, "dataseries.[].unit", "can be bound to data")],
    ),
    "condition on a value the enum lacks": (
        lambda r: edit_json(r, SCHEMA, lambda s: with_style_condition(s, ["plain", "fancy"])),
        [("ERROR", SCHEMA, "dataseries.[].unit", "'fancy' is not one of the target's enum values")],
    ),
    "notFor that routes nowhere": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["aiSelection"]["notFor"].append("Anything with a map.")),
        [("WARN", SCHEMA, "aiSelection.notFor.1", "names no widget")],
    ),
    "dataShape as a list": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["aiSelection"].update(dataShape=["numbers"])),
        [("ERROR", SCHEMA, "aiSelection.dataShape", "non-empty string")],
    ),
    "layout size without its flag": (
        lambda r: edit_json(r, SCHEMA, lambda s: s.update(layout={"height": 48})),
        [("ERROR", SCHEMA, "layout.fixedHeight", "only counts together with fixedHeight")],
    ),
    "layout flag without a size": (
        lambda r: edit_json(r, SCHEMA, lambda s: s.update(layout={"fixedWidth": True})),
        [("ERROR", SCHEMA, "layout.width", "natural width in pixels")],
    ),
    "TODO left in the schema": (
        lambda r: edit_json(r, SCHEMA, lambda s: s["aiSelection"]["useWhen"].append("TODO: more")),
        [("ERROR", SCHEMA, "aiSelection.useWhen.1", "TODO")],
    ),
    # -- default config ------------------------------------------------------
    "undeclared default key": (
        lambda r: edit_json(r, DEFAULTS, lambda d: d.update(subtitle="typo")),
        [("ERROR", DEFAULTS, "subtitle", "not declared")],
    ),
    "prefixed default value": (
        lambda r: edit_json(r, DEFAULTS, lambda d: d.update(title="$str:Metrics")),
        [("ERROR", DEFAULTS, "title", "prefix")],
    ),
    "default of the wrong type": (
        lambda r: edit_json(r, DEFAULTS, lambda d: d["dataseries"][0].update(precision="1")),
        [("ERROR", DEFAULTS, "dataseries.0.precision", "where the schema says number")],
    ),
    "default above the maximum": (
        lambda r: edit_json(r, DEFAULTS, lambda d: d["dataseries"][0].update(precision=9)),
        [("ERROR", DEFAULTS, "dataseries.0.precision", "above the maximum")],
    ),
    "default for a hidden field": (
        lambda r: (
            edit_json(
                r,
                SCHEMA,
                lambda s: (
                    series_item(s).update(showUnit={"title": "Show Unit", "description": "Show the unit.", "type": "boolean", "dataDrivenDisabled": True, "order": 6}),
                    series_item(s)["unit"].update(condition={"relativePath": "../showUnit", "showIfValueIn": [True]}),
                ),
            ),
            edit_json(r, DEFAULTS, lambda d: d["dataseries"][0].update(unit="rpm")),
        ),
        [("WARN", DEFAULTS, "dataseries.0.unit", "condition")],
    ),
    # -- types, thumbnails, docs, dist ----------------------------------------
    "types not regenerated after a title change": (
        lambda r: edit_json(r, SCHEMA, lambda s: s.update(title="Readout Configuration")),
        [("ERROR", "src/definition-schema.d.ts", "-", "ReadoutConfiguration")],
    ),
    "no thumbnails": (
        lambda r: ((r / "thumbnail.png").unlink(), (r / "thumbnail.webp").unlink()),
        [("ERROR", "thumbnail.webp", "-", "no thumbnail")],
    ),
    "thumbnail in the wrong format": (
        lambda r: shutil.copy(r / "thumbnail.png", r / "thumbnail.webp"),
        [("ERROR", "thumbnail.webp", "-", "not a webp image")],
    ),
    "TODO left in the README": (
        lambda r: edit(r, "README.md", lambda t: t + "\nTODO: usage\n"),
        [("ERROR", "README.md", "TODO", "template text")],
    ),
    "hard-coded tag in the README": (
        lambda r: edit(r, "README.md", lambda t: t + "\n<widget-sample-1.0.0></widget-sample-1.0.0>\n"),
        [("WARN", "README.md", "-", "hard-codes the tag")],
    ),
    "stale dist": (
        lambda r: ((r / "dist").mkdir(), (r / "dist/widget-sample.js").write_text('import { LitElement } from "lit";\ncustomElement("widget-sample-0.9.0");\n')),
        [("WARN", "dist/widget-sample.js", "-", "rebuild")],
    ),
    "dist import the host cannot resolve": (
        lambda r: ((r / "dist").mkdir(), (r / "dist/widget-sample.js").write_text('import { debounce } from "lodash-es";\ncustomElement("widget-sample-1.0.0");\n')),
        [("ERROR", "dist/widget-sample.js", "lodash-es", "fails to load on cloud")],
    ),
    "dist split into chunks": (
        lambda r: ((r / "dist").mkdir(), (r / "dist/widget-sample.js").write_text('import "./chunk-a.js";\ncustomElement("widget-sample-1.0.0");\n')),
        [("ERROR", "dist/widget-sample.js", "./chunk-a.js", "one file")],
    ),
}

# name: mutation of a finished widget that is correct, so the checker must
# report nothing (a positive control for a check that once misfired).
ACCEPTED: dict[str, Mutation] = {
    # false matches an unset enum target in the editor, the AI and the board
    # validator (widget-form shows Target Column before a field type is picked).
    "false in an enum condition": lambda r: edit_json(r, SCHEMA, lambda s: with_style_condition(s, ["plain", False])),
}


def main() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1. The scaffolder.
        for bad in ("Sample", "sample_x", "-x", "widget-"):
            if run(str(NEW_WIDGET), bad, "--dest", str(base / "bad")).returncode == 0:
                print(f"FAIL new_widget.py accepted the name {bad!r}")
                failed += 1
        (base / "occupied").mkdir()
        (base / "occupied" / "keep.txt").write_text("x")
        if run(str(NEW_WIDGET), "sample", "--dest", str(base / "occupied")).returncode == 0:
            print("FAIL new_widget.py wrote into a folder that is not empty")
            failed += 1
        scaffold = base / "scaffold" / "widget-sample"
        done = run(str(NEW_WIDGET), "sample", "--dest", str(scaffold))
        if done.returncode != 0:
            sys.exit(f"new_widget.py failed:\n{done.stdout}{done.stderr}")
        leftovers = [
            str(p.relative_to(scaffold))
            for p in scaffold.rglob("*")
            if p.is_file() and p.suffix != ".webp" and re.search(r"(?i)starter", p.name + p.read_text(errors="replace"))
        ]
        if leftovers or not (scaffold / ENTRY).is_file():
            print(f"FAIL the scaffold still says 'starter' in {leftovers}" if leftovers else f"FAIL no {ENTRY}")
            failed += 1
        else:
            print("ok   new_widget.py: names, refusals and renames")

        # 2. The scaffold as generated: only its TODOs and the missing thumbnails.
        raw = findings(scaffold)
        expected_raw = {
            ("ERROR", "src/definition-schema.json", "description"),
            ("ERROR", "src/definition-schema.json", "aiSelection.dataShape"),
            ("ERROR", "src/definition-schema.json", "aiSelection.useWhen.0"),
            ("ERROR", "src/definition-schema.json", "aiSelection.notFor.0"),
            ("ERROR", "package.json", "description"),
            ("ERROR", "README.md:3", "TODO"),
            ("ERROR", "thumbnail.webp", "-"),
        }
        got = {(level, where, path) for level, where, path, _ in raw}
        unexpected = sorted(f for f in raw if (f[0], f[1], f[2]) not in expected_raw and not f[1].startswith(("CLAUDE.md", "package-lock.json")))
        missing = sorted(expected_raw - got)
        status = "ok  " if not unexpected and not missing else "FAIL"
        print(f"{status} the scaffold as generated: {len(raw)} finding(s)")
        for problem in [f"missing {m}" for m in missing] + [f"unexpected {u}" for u in unexpected]:
            print(f"     {problem}")
        failed += status == "FAIL"

        # 3. A finished scaffold is clean.
        finished = base / "finished" / "widget-sample"
        shutil.copytree(scaffold, finished)
        finish(finished)
        clean = findings(finished)
        status = "ok  " if not clean else "FAIL"
        print(f"{status} a finished widget: {len(clean)} finding(s)")
        for f in clean:
            print(f"     unexpected {f}")
        failed += status == "FAIL"

        # 4. Every mutation is reported.
        for name, (mutate, expected) in MUTATIONS.items():
            repo = base / "mutations" / name.replace(" ", "-") / "widget-sample"
            shutil.copytree(finished, repo)
            mutate(repo)
            found = findings(repo)
            problems = [
                f"missing {level} {file} {path} :: {text}"
                for level, file, path, text in expected
                if not any(f[0] == level and f[1].split(":")[0] == file and f[2] == path and text in f[3] for f in found)
            ]
            status = "ok  " if not problems else "FAIL"
            print(f"{status} {name}")
            for problem in problems:
                print(f"     {problem}")
            if problems:
                for f in found:
                    print(f"     found {f}")
            failed += bool(problems)

        # 5. Correct shapes stay clean.
        for name, mutate in ACCEPTED.items():
            repo = base / "accepted" / name.replace(" ", "-") / "widget-sample"
            shutil.copytree(finished, repo)
            mutate(repo)
            found = findings(repo)
            status = "ok  " if not found else "FAIL"
            print(f"{status} accepted: {name}")
            for f in found:
                print(f"     unexpected {f}")
            failed += bool(found)
    print(f"\n{failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
