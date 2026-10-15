#!/usr/bin/env python3
"""Set up and grade the ironflock-widgets skill evals.

    python3 evals/widgets/grade.py setup <iteration-dir>
    python3 evals/widgets/grade.py grade <iteration-dir>

`setup` creates <iteration-dir>/<eval>/<config>/ironflock-widgets/ for both
configs (with_skill, without_skill) and clones each eval's fixtures from
evals.json into it. Fixtures that a prompt edits are checked out at their pinned
commit with the `origin` remote removed, so a run cannot push or release; the
other repos are copied without history, as examples.

Then run every prompt in evals.json once per config, in that config's folder,
with an agent that reads the skill (with_skill) or doesn't (without_skill). Tell
the agents never to publish, release, commit or push, and have each one's final
report saved as <iteration-dir>/<eval>/<config>/REPORT.md.

`grade` builds each result, runs check_widget.py on it, writes grading.json
(fields text / passed / evidence, as the skill-creator viewer expects) next to
REPORT.md and prints pass rates per configuration. Needs git, npm and network.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALS = json.loads((HERE / "evals.json").read_text())
SCRIPTS = HERE.parent.parent / "plugins/ironflock/skills/ironflock-widgets/scripts"
CHECK = SCRIPTS / "check_widget.py"
CONFIGS = ("with_skill", "without_skill")
FINDING = re.compile(r"^(ERROR|WARN)\s+(\S+) (\S+): (.*)$")

sys.path.insert(0, str(SCRIPTS))
from check_widget import find_node_binary  # noqa: E402

NODE = find_node_binary()
ENV = {**os.environ, "PATH": (str(Path(NODE).parent) + os.pathsep if NODE else "") + os.environ["PATH"]}


def sh(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=ENV, timeout=timeout)


def setup(iteration: Path) -> None:
    for spec in EVALS["evals"]:
        edited = {spec["fixture"][0]} if spec["name"] != "new-widget" else set()
        for config in CONFIGS:
            folder = iteration / spec["name"] / config / "ironflock-widgets"
            folder.mkdir(parents=True, exist_ok=False)
            for name in spec["fixture"]:
                fixture = EVALS["fixtures"][name]
                target = folder / name
                if name in edited:
                    sh(["git", "clone", "--quiet", fixture["repo"], str(target)], folder).check_returncode()
                    sh(["git", "checkout", "--quiet", fixture["commit"]], target).check_returncode()
                    sh(["git", "remote", "remove", "origin"], target).check_returncode()
                else:
                    sh(["git", "clone", "--quiet", "--depth", "1", fixture["repo"], str(target)], folder).check_returncode()
                    shutil.rmtree(target / ".git")
            print(f"ready: {folder}")


def findings(repo: Path, *flags: str) -> list[tuple[str, str, str, str]]:
    done = sh([sys.executable, "-B", str(CHECK), str(repo), *flags], repo)
    return [(m[1], m[2], m[3], m[4]) for m in map(FINDING.match, done.stdout.splitlines()) if m]


def build(repo: Path) -> tuple[bool, str]:
    if not (repo / "node_modules").is_dir():
        install = sh(["npm", "install", "--no-audit", "--no-fund"], repo)
        if install.returncode:
            return False, "npm install failed: " + install.stderr[-300:]
    done = sh(["npm", "run", "build"], repo)
    return done.returncode == 0, (done.stdout + done.stderr)[-300:].strip()


def item(text: str, passed: Any, evidence: str) -> dict:
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def untouched(repo: Path, name: str) -> list[dict]:
    fixture = EVALS["fixtures"][name]
    head = sh(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
    tags = sh(["git", "tag", "--points-at", "HEAD"], repo).stdout.split()
    version = json.loads((repo / "package.json").read_text())["version"]
    return [
        item("no commits or tags", head == fixture["commit"] and tags == [fixture["tag"]], f"HEAD {head}, tags {tags}"),
        item("version not bumped (no release)", version == fixture["tag"], f"version {version}"),
    ]


def schema_properties(node: dict, path: str = ""):
    for key, child in (node.get("properties") or {}).items():
        yield f"{path}{key}", child
        yield from schema_properties(child, f"{path}{key}.")
        if isinstance(child.get("items"), dict):
            yield from schema_properties(child["items"], f"{path}{key}[].")


def grade_edit_value(run: Path) -> list[dict]:
    repo = run / "ironflock-widgets/widget-value"
    ok, log = build(repo)
    out = [item("npm run build passes", ok, log), *untouched(repo, "widget-value")]
    before = sh(["git", "show", "HEAD:src/definition-schema.json"], repo).stdout
    old = dict(schema_properties(json.loads(before)))
    schema = json.loads((repo / "src/definition-schema.json").read_text())
    new = {k: v for k, v in schema_properties(schema) if k not in old and k.startswith("dataseries[].")}
    out.append(item(
        "schema adds a numeric threshold and a colour per value display",
        any(v.get("type") == "number" for v in new.values()) and any(v.get("type") == "color" for v in new.values()),
        f"new: {sorted(new)}",
    ))
    complete = new and all(all(v.get(f) not in (None, "") for f in ("title", "description", "type", "order")) for v in new.values())
    out.append(item("new properties have title, description, type and order", complete, json.dumps({k: sorted(v) for k, v in new.items()})))
    dts = (repo / "src/definition-schema.d.ts").read_text()
    out.append(item("generated types contain the new properties", new and all(k.split(".")[-1] in dts for k in new), ", ".join(new)))
    since = findings(repo, "--since", "HEAD")
    out.append(item("check_widget.py --since HEAD: no new errors", not [f for f in since if f[0] == "ERROR"], json.dumps(since)[:600]))
    out.append(item("check_widget.py --since HEAD: no new warnings", not since, json.dumps(since)[:600]))
    return out


def grade_fix_gauge(run: Path) -> list[dict]:
    repo = run / "ironflock-widgets/widget-gauge"
    ok, log = build(repo)
    out = [item("npm run build passes", ok, log), *untouched(repo, "widget-gauge")]
    report = (run / "REPORT.md").read_text() if (run / "REPORT.md").exists() else ""
    cause = re.search(r"epoch|millisecond", report, re.I) and re.search(r"Date\.parse|NaN", report)
    out.append(item("the report names the cause: epoch-ms timestamps become NaN in Date.parse", cause, report[:300]))
    still = [f for f in findings(repo) if "Date.parse() on a timestamp" in f[3]]
    out.append(item("no Date.parse() on the timestamp any more", not still, json.dumps(still)))
    code = (repo / "src/widget-gauge.ts").read_text()
    calls = {name for name in re.findall(r"(\w+)\([^\n]*?\.tsp\b", code) if name not in ("parse", "Date")}
    helpers = sorted(
        name for name in calls
        if re.search(rf"(?:function\s+{name}\b|\b{name}\s*=\s*\()[\s\S]{{0,600}}?(?:typeof [^\n]*'number'|Number\(|\\d)", code)
    )
    out.append(item("the timestamp goes through a parser that accepts numbers", helpers, f"tsp passed to {sorted(calls)}; numeric-aware: {helpers}"))
    since = findings(repo, "--since", "HEAD")
    out.append(item("check_widget.py --since HEAD: no new errors", not [f for f in since if f[0] == "ERROR"], json.dumps(since)[:600]))
    return out


def grade_new_widget(run: Path) -> list[dict]:
    repo = run / "ironflock-widgets/widget-progress"
    if not (repo / "package.json").exists():
        return [item("widget-progress repository exists", False, "no package.json")]
    pkg = json.loads((repo / "package.json").read_text())
    out = [item(
        "package is @ironflock/widget-progress with main dist/widget-progress.js",
        pkg.get("name") == "@ironflock/widget-progress" and str(pkg.get("main", "")).lstrip("./") == "dist/widget-progress.js",
        f"name {pkg.get('name')}, main {pkg.get('main')}",
    )]
    ok, log = build(repo)
    out.append(item("npm run build passes", ok, log))
    bundle = repo / "dist/widget-progress.js"
    tag = f"widget-progress-{pkg.get('version')}"
    out.append(item("the bundle registers widget-progress-<version>", bundle.exists() and tag in bundle.read_text(), tag))
    found = findings(repo)
    errors = [f for f in found if f[0] == "ERROR" and not f[1].startswith("thumbnail")]
    out.append(item("check_widget.py: no errors (thumbnails aside)", not errors, json.dumps(errors)[:600]))
    out.append(item("thumbnails present", not [f for f in found if f[1].startswith("thumbnail") and f[0] == "ERROR"], ""))
    warnings = [f for f in found if f[0] == "WARN"]
    out.append(item("check_widget.py: at most 2 warnings", len(warnings) <= 2, json.dumps(warnings)[:600]))
    schema = json.loads((repo / "src/definition-schema.json").read_text()) if (repo / "src/definition-schema.json").exists() else {}
    selection = schema.get("aiSelection") or {}
    routes = any(re.search(r"widget-[a-z]", n) for n in selection.get("notFor") or [] if isinstance(n, str))
    out.append(item(
        "aiSelection with dataShape, useWhen and a notFor that names another widget",
        isinstance(selection.get("dataShape"), str) and selection.get("useWhen") and routes,
        json.dumps(selection)[:300],
    ))
    rows = [p for p, n in schema_properties(schema) if n.get("type") == "array" and not n.get("dataDrivenDisabled") and len((n.get("items") or {}).get("properties") or {}) >= 3]
    out.append(item("a bindable array of rows (label, value, target)", rows, ", ".join(rows)))
    report = (run / "REPORT.md").read_text() if (run / "REPORT.md").exists() else ""
    # The steps themselves are internal; the report has to name the work in Studio and the platform.
    platform = re.search(r"\bStudio\b", report) and re.search(r"regist|palette|platform|database", report, re.I)
    out.append(item("the report lists the platform registration still needed", platform, report[:300]))
    head = sh(["git", "rev-parse", "HEAD"], repo)
    out.append(item("no commits in the new repository", head.returncode != 0, head.stdout.strip() or "no HEAD"))
    view = sh(["npm", "view", "@ironflock/widget-progress", "version"], repo, timeout=60)
    out.append(item("nothing was published to npm", view.returncode != 0, (view.stdout + view.stderr).strip()[:120]))
    return out


GRADERS = {"edit-value": grade_edit_value, "fix-gauge": grade_fix_gauge, "new-widget": grade_new_widget}


def grade(iteration: Path) -> None:
    totals: dict[str, list[int]] = {}
    for spec in EVALS["evals"]:
        for config in CONFIGS:
            run = iteration / spec["name"] / config
            if not run.is_dir():
                continue
            results = GRADERS[spec["name"]](run)
            (run / "grading.json").write_text(json.dumps({"expectations": results}, indent=2) + "\n")
            passed = sum(r["passed"] for r in results)
            totals.setdefault(config, [0, 0])
            totals[config][0] += passed
            totals[config][1] += len(results)
            print(f"\n{spec['name']} / {config}: {passed}/{len(results)}")
            for r in results:
                print(f"  {'pass' if r['passed'] else 'FAIL'} {r['text']}" + ("" if r["passed"] else f"  [{r['evidence'][:200]}]"))
    print()
    for config, (passed, total) in totals.items():
        print(f"{config}: {passed}/{total} ({passed / total:.0%})")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("setup", "grade"):
        print(__doc__, file=sys.stderr)
        return 2
    iteration = Path(sys.argv[2]).resolve()
    setup(iteration) if sys.argv[1] == "setup" else grade(iteration)
    return 0


if __name__ == "__main__":
    sys.exit(main())
