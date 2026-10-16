#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6.0", "jsonschema>=4.18"]
# ///
"""Grade one iteration of the skill evals.

    uv run evals/grade.py <iteration-dir>

Expects <iteration-dir>/<eval-name>/<config>/app, where each app is a copy of
evals/fixtures/machine-monitor that an agent changed for the eval prompt in
evals/evals.json. Writes <iteration-dir>/<eval-name>/<config>/grading.json
(fields text / passed / evidence, as the skill-creator viewer expects) and
prints pass rates per configuration.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins/ironflock/skills/ironflock-templates/scripts"
sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402
from validate import Yaml12Loader  # noqa: E402


def load(path: Path):
    try:
        return yaml.load(path.read_text(), Loader=Yaml12Loader) if path.exists() else None
    except yaml.YAMLError:
        return None


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, path + (k,))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, path + (i,))


def refs(widget):
    """(kind, ref) for every binding in a widget's chartconfig."""
    for _, v in walk(widget.get("chartconfig")):
        if isinstance(v, dict):
            for kind in ("valueRef", "tableRef"):
                if isinstance(v.get(kind), dict):
                    yield kind, v[kind]


def ref_columns(kind, ref):
    if kind == "valueRef":
        return {str(ref.get("column", "")).split(".")[0]}
    return {v for _, v in walk(ref.get("format")) if isinstance(v, str) and "$" not in v}


def window_hours(ref):
    qp = ref.get("queryParams") or {}
    unit = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168}.get(qp.get("windowPeriod"))
    length = qp.get("windowLength")
    return unit * length if unit and isinstance(length, (int, float)) else None


def has_latest(ref):
    return any(isinstance(f, dict) and f.get("latest") for f in (ref.get("queryParams") or {}).get("filterAnd") or [])


def run_validator(app: Path):
    done = subprocess.run([sys.executable, str(SCRIPTS / "validate.py"), str(app)], capture_output=True, text=True)
    lines = done.stdout.splitlines()
    errors = [line for line in lines if line.startswith("ERROR")]
    warnings = [line for line in lines if line.startswith("WARN")]
    return errors, warnings


def check(text, passed, evidence):
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def grade_overview(app: Path, errors, warnings):
    board = load(app / ".ironflock/board-template.yml") or {}
    data = load(app / ".ironflock/data-template.yml") or {}
    widgets = [w for w in board.get("widgets") or [] if isinstance(w, dict)]
    by_pkg = defaultdict(list)
    for w in widgets:
        by_pkg[w.get("package_name")].append(w)
    gauge = any(
        "temperature" in ref_columns(k, r) and r.get("tablename") == "measurements"
        for w in by_pkg["widget-gauge"]
        for k, r in refs(w)
    )
    trend_cols, trend_24 = set(), False
    for w in by_pkg["widget-linechart"]:
        for k, r in refs(w):
            if k == "tableRef" and r.get("tablename") == "measurements":
                trend_cols |= ref_columns(k, r)
                trend_24 |= window_hours(r) == 24
    state = any(
        "state" in ref_columns(k, r) and r.get("tablename") == "machine_status" and has_latest(r)
        for w in widgets
        for k, r in refs(w)
    )
    transforms = {t.get("tablename"): t for t in (data.get("data") or {}).get("transforms") or [] if isinstance(t, dict)}
    power = [
        (k, r)
        for w in widgets
        for k, r in refs(w)
        if "power_kw" in ref_columns(k, r) or "power_kw" in str((transforms.get(r.get("tablename")) or {}).get("sql", ""))
    ]
    coverage = [w for w in warnings if "widgets cover" in w]
    return [
        check("board-template.yml exists", board, "present" if board else "missing"),
        check("validate.py reports no errors", not errors, f"{len(errors)} error(s)" + (f": {errors[0][:160]}" if errors else "")),
        check("gauges bind measurements.temperature", gauge, f"{len(by_pkg['widget-gauge'])} gauge widget(s)"),
        check(
            "a line chart shows temperature and vibration over a 24 h window",
            {"temperature", "vibration"} <= trend_cols and trend_24,
            f"columns {sorted(trend_cols)}, 24h window: {trend_24}",
        ),
        check("a widget shows machine_status.state with the latest-per-entity filter", state, "found" if state else "not found"),
        check("a widget binds power_kw (directly or through a transform)", power, f"{len(power)} binding(s)"),
        check("every page fills the grid", board and not coverage, coverage[0][:160] if coverage else "no coverage warnings"),
    ]


def grade_multipage(app: Path, errors, warnings):
    board = load(app / ".ironflock/board-template.yml") or {}
    widgets = [w for w in board.get("widgets") or [] if isinstance(w, dict)]
    layout = board.get("layout") if isinstance(board.get("layout"), dict) else {}

    def pages(page, route=()):
        yield route, page
        for name, child in (page.get("subRoutes") or {}).items():
            if isinstance(child, dict):
                yield from pages(child, route + (str(name),))

    all_pages = list(pages(layout)) if layout else []
    wildcard = [(r, p) for r, p in all_pages if r and r[-1] == "*"]
    by_id = {w.get("layout_id"): w for w in widgets}
    route_filtered = []
    for route, page in wildcard:
        for pos in page.get("gridLayout") or []:
            w = by_id.get(pos.get("id")) if isinstance(pos, dict) else None
            for k, r in refs(w or {}):
                for f in (r.get("queryParams") or {}).get("filterAnd") or []:
                    if isinstance(f, dict) and f.get("useRoute") and f.get("column") == "machine_id":
                        route_filtered.append((route, str(f.get("value")), len(route)))
    seg_ok = bool(route_filtered) and all(v.isdigit() and int(v) == n for _, v, n in route_filtered)
    route_warn = [w for w in warnings if "matches no page" in w]
    sidenav = any(w.get("package_name") == "widget-sidenav" for w in widgets)
    return [
        check("board-template.yml exists", board, "present" if board else "missing"),
        check("validate.py reports no errors", not errors, f"{len(errors)} error(s)" + (f": {errors[0][:160]}" if errors else "")),
        check("uses widget-sidenav", sidenav, "found" if sidenav else "not found"),
        check("has a wildcard (*) detail page", wildcard, f"pages: {['/' + '/'.join(r) for r, _ in all_pages]}"),
        check(
            "detail widgets filter machine_id by the wildcard's route segment",
            seg_ok,
            f"useRoute filters (page, value, expected index): {route_filtered[:4]}",
        ),
        check("every navigation route leads to a page", board and not route_warn, route_warn[0][:160] if route_warn else "no route warnings"),
    ]


def grade_ports(app: Path, errors, warnings):
    ports = (load(app / ".ironflock/port-template.yml") or {}).get("ports") or []
    env = load(app / ".ironflock/env-template.yml") or {}
    data = load(app / ".ironflock/data-template.yml") or {}
    main_py = (app / "main.py").read_text() if (app / "main.py").exists() else ""
    port = [p for p in ports if isinstance(p, dict) and p.get("port") == 8080]
    port_ok = bool(port) and port[0].get("protocol", "http") in ("http", "https") and port[0].get("main") is True
    var = env.get("SAMPLE_INTERVAL") if isinstance(env, dict) else None
    var_ok = (
        isinstance(var, dict)
        and var.get("type") == "numeric"
        and var.get("min") == 1
        and var.get("max") == 60
        and var.get("defaultValue") == 5
    )
    tables = {t.get("tablename"): t for t in (data.get("data") or {}).get("tables") or [] if isinstance(t, dict)}
    cols = (tables.get("measurements") or {}).get("columns") or []
    rpm = [c for c in cols if isinstance(c, dict) and re.search(r"rpm|speed", f"{c.get('id')} {c.get('description')}", re.I)]
    rpm_ok = bool(rpm) and rpm[0].get("dataType") in ("numeric", "bigint")
    published = bool(rpm) and re.search(rf"[\"']{re.escape(str(rpm[0].get('id')))}[\"']\s*:", main_py)
    return [
        check("validate.py reports no errors", not errors, f"{len(errors)} error(s)" + (f": {errors[0][:160]}" if errors else "")),
        check("port-template declares 8080 as the main http port", port_ok, f"ports: {ports}"),
        check("env-template: SAMPLE_INTERVAL numeric, 1..60, default 5", var_ok, f"SAMPLE_INTERVAL: {var}"),
        check("data-template: measurements has a numeric rpm column", rpm_ok, f"rpm columns: {[c.get('id') for c in rpm]}"),
        check("main.py publishes the rpm column", published, "publishes it" if published else "not found in main.py"),
    ]


def grade_new_app(app: Path, errors, warnings):
    board = load(app / ".ironflock/board-template.yml") or {}
    data = load(app / ".ironflock/data-template.yml") or {}
    ports = (load(app / ".ironflock/port-template.yml") or {}).get("ports") or []
    files = [p for p in app.rglob("*") if p.is_file() and not {".git", "node_modules", ".venv"} & set(p.parts)]
    code = "\n".join(p.read_text(errors="ignore") for p in files if p.suffix in (".py", ".js", ".mjs", ".ts", ".go"))
    pages = "\n".join(p.read_text(errors="ignore") for p in files if p.suffix in (".html", ".js", ".mjs", ".ts", ".tsx"))
    setup = "\n".join(p.read_text(errors="ignore") for p in files if p.name.startswith(("Dockerfile", "docker-compose")))
    widgets = [w for w in board.get("widgets") or [] if isinstance(w, dict)]
    tables = {t.get("tablename"): t for t in (data.get("data") or {}).get("tables") or [] if isinstance(t, dict)}

    # The table a board form writes a numeric limit into, and whether the code follows it.
    form_tables = {
        str((f.get("targetColumn") or {}).get("tablename"))
        for w in widgets if w.get("package_name") == "widget-form"
        for f in (w.get("chartconfig") or {}).get("formFields") or [] if isinstance(f, dict) and isinstance(f.get("targetColumn"), dict)
    }
    limit_tables = [
        name for name in form_tables
        if any(isinstance(c, dict) and c.get("dataType") in ("numeric", "bigint") and re.search(r"limit|low|min|threshold|alarm", str(c.get("id")), re.I)
               for c in (tables.get(name) or {}).get("columns") or [])
    ]

    constants = re.findall(r"\b([A-Za-z_]\w*)\s*(?::\s*\w+\s*)?:?=\s*[\"']([^\"'\n]+)[\"']", code)

    def called(functions, table):
        """A call that names the table, as a string or through a constant that holds it."""
        names = [re.escape(f'"{table}"'), re.escape(f"'{table}'")]
        names += [rf"\b{name}\b" for name, value in constants if value == table]
        return re.search(rf"(?:{functions})\s*\(\s*(?:ctx\s*,\s*)?(?:{'|'.join(names)})", code)

    follows = [t for t in limit_tables if called("subscribe_to_table|subscribeToTable|SubscribeToTable", t) and called("getHistory|GetHistory", t)]
    rejoin = re.search(r"""\.on\(\s*["']join["']|on_join|onJoin|OnJoin""", code)

    http_ports = [p.get("port") for p in ports if isinstance(p, dict) and p.get("protocol", "http") in ("http", "https")]
    served = [p for p in http_ports if re.search(rf"\b{p}\b", code + setup)]
    tunnel_url = re.search(r"getRemoteAccessUrlForPort|GetRemoteAccessURLForPort", code)

    def pages_of(page, route=()):
        yield route, page
        for name, child in (page.get("subRoutes") or {}).items():
            if isinstance(child, dict):
                yield from pages_of(child, route + (str(name),))

    layout = board.get("layout") if isinstance(board.get("layout"), dict) else {}
    wildcard = [p for r, p in pages_of(layout) if r and r[-1] == "*"] if layout else []
    on_wildcard = {pos.get("id") for p in wildcard for pos in p.get("gridLayout") or [] if isinstance(pos, dict)}
    embeds = [
        w for w in widgets
        if w.get("package_name") == "widget-embed" and w.get("layout_id") in on_wildcard
        and isinstance(((w.get("chartconfig") or {}).get("webUrl") or {}), dict)
        and ((w["chartconfig"]["webUrl"].get("valueRef") or {}).get("tablename") in tables)
        and any(isinstance(f, dict) and f.get("useRoute") for f in ((w["chartconfig"]["webUrl"]["valueRef"].get("queryParams") or {}).get("filterAnd") or []))
    ]
    pushed = re.search(r"WebSocket|EventSource", pages)
    sigterm = re.search(r"SIGTERM", code) or re.search(r"init:\s*true|tini|dumb-init", setup)
    return [
        check("validate.py reports no errors", not errors, f"{len(errors)} error(s)" + (f": {errors[0][:160]}" if errors else "")),
        check("a Dockerfile or docker-compose.yml and edge code using the ironflock SDK", setup and re.search(r"ironflock", code), f"{len(files)} file(s)"),
        check("a board form writes the low-level limit into a table", limit_tables, f"form tables {sorted(form_tables)}"),
        check("the code reads that table at start and subscribes to it", follows, f"followed: {follows}"),
        check("the code reads the limit again after a reconnect", rejoin, rejoin.group(0) if rejoin else "no join hook"),
        check("port-template declares the web page's http port, and the code serves it", served, f"http ports {http_ports}"),
        check("the code writes the port's tunnel URL into a table", tunnel_url, "found" if tunnel_url else "not found"),
        check("a widget-embed on a per-tank page binds the URL from a table, filtered by the route", embeds, f"{len(embeds)} embed(s), {len(wildcard)} wildcard page(s)"),
        check("the web page is pushed to (websocket or server-sent events)", pushed, pushed.group(0) if pushed else "no push channel"),
        check("the program stops on SIGTERM", sigterm, sigterm.group(0) if sigterm else "not handled"),
    ]


GRADERS = {
    "overview-board": grade_overview,
    "multi-page-navigation": grade_multipage,
    "ports-params-data": grade_ports,
    "new-app": grade_new_app,
}


def main() -> int:
    iteration = Path(sys.argv[1]).resolve()
    totals = defaultdict(lambda: [0, 0])
    for eval_dir in sorted(p for p in iteration.iterdir() if p.is_dir() and p.name in GRADERS):
        for run in sorted(p for p in eval_dir.iterdir() if (p / "app").is_dir()):
            errors, warnings = run_validator(run / "app")
            results = GRADERS[eval_dir.name](run / "app", errors, warnings)
            passed = sum(r["passed"] for r in results)
            (run / "grading.json").write_text(
                json.dumps(
                    {
                        "expectations": results,
                        "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results), "pass_rate": passed / len(results)},
                        "validator": {"errors": errors, "warnings": warnings},
                    },
                    indent=2,
                )
            )
            totals[run.name][0] += passed
            totals[run.name][1] += len(results)
            print(f"{eval_dir.name:24} {run.name:14} {passed}/{len(results)}  ({len(errors)} errors, {len(warnings)} warnings)")
            for r in results:
                if not r["passed"]:
                    print(f"{'':40}✗ {r['text']} — {r['evidence'][:110]}")
    for config, (p, t) in sorted(totals.items()):
        print(f"{config}: {p}/{t} = {p / t:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
