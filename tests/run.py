#!/usr/bin/env python3
"""Regression tests for the skill's validator and its starter app.

    python3 tests/run.py

For the skill's references/example-board.yml and every tests/boards/<name>.yml:
copy tests/app (an app with a data-template.yml) to a temporary folder, add the
board as board-template.yml, run scripts/validate.py and compare its findings:

- the example board must produce no findings at all;
- every other board must produce each finding its `# expect:` lines list, as
  `# expect: LEVEL <exact path> :: <part of the message>`, and no finding at a
  path its `# expect-none: <exact path>` lines list.

Then the starter app: assets/app-template must produce no findings at all, and
scripts/new_app.py must scaffold an app from it that keeps no trace of the
starter's name, produces no findings either, and is never overwritten.

Then privileged access: scripts/compose_privileges.py must classify every case
of privileged-compose-fixture.json (a byte-identical copy of the test vectors
the platform and the device agent share) exactly as its `features` say, and
validate.py must report each of those settings when data-template.yml does not
declare `privileged`, nothing when it does, and the declaration itself when the
compose file requests no privileged settings. `include` and `extends` with a
file are reported either way, as files to merge into docker-compose.yml.

Needs network access for the widget schemas (cached after the first run).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parent / "plugins/ironflock/skills/ironflock-templates"
VALIDATE = SKILL / "scripts/validate.py"
EXAMPLE = SKILL / "references/example-board.yml"
STARTER = SKILL / "assets/app-template"
NEW_APP = SKILL / "scripts/new_app.py"
FIXTURE = ROOT / "privileged-compose-fixture.json"
FINDING = re.compile(r"^(ERROR|WARN)\s+(\S+) (\S+): (.*)$")
EXPECT = re.compile(r"^# expect:\s*(ERROR|WARN)\s+(\S+)\s+::\s+(.*)$")
EXPECT_NONE = re.compile(r"^# expect-none:\s*(\S+)\s*$")


def validate(app: Path, name: str) -> list[tuple[str, str, str]]:
    done = subprocess.run([sys.executable, str(VALIDATE), str(app)], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        sys.exit(f"validate.py crashed on {name}:\n{done.stdout}{done.stderr}")
    return [(m[1], m[3], m[4]) for m in map(FINDING.match, done.stdout.splitlines()) if m]


def run_board(board: Path) -> list[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        app = Path(tmp) / "app"
        shutil.copytree(ROOT / "app", app)
        shutil.copy(board, app / ".ironflock" / "board-template.yml")
        return validate(app, board.name)


def check_starter() -> list[str]:
    """Problems with the starter app and with an app new_app.py scaffolds from it."""
    problems = [f"unexpected {lvl} {path}: {msg}" for lvl, path, msg in validate(STARTER, "the starter app")]
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "tank-monitor"
        (dest / ".git").mkdir(parents=True)  # a fresh clone of an empty repository
        new_app = [sys.executable, str(NEW_APP), "tank-monitor", "--dest", str(dest)]
        done = subprocess.run(new_app, capture_output=True, text=True)
        if done.returncode:
            return problems + [f"new_app.py failed: {done.stderr.strip()}"]
        copied = {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
        starter = {p.relative_to(STARTER) for p in STARTER.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        problems += [f"new_app.py did not copy {path}" for path in sorted(starter - copied)]
        for path in sorted(copied):
            text = (dest / path).read_text(encoding="utf-8")
            if "app-starter" in text or "App Starter" in text:
                problems.append(f"the starter's name is left in {path}")
        problems += [f"unexpected {lvl} {path}: {msg}" for lvl, path, msg in validate(dest, "the scaffolded app")]
        if subprocess.run(new_app, capture_output=True, text=True).returncode == 0:
            problems.append("new_app.py wrote into an existing app")
    return problems


def check_privileged() -> tuple[int, list[str]]:
    """Problems with the compose classifier and with validate.py's privileged check."""
    sys.path.insert(0, str(SKILL / "scripts"))
    import compose_privileges

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    problems = []
    if list(compose_privileges.SERVICE_KEYS) != fixture["serviceKeyOrder"]:
        problems.append("compose_privileges.SERVICE_KEYS is not the fixture's serviceKeyOrder")
    problems += check_classifier_shapes(compose_privileges, fixture["topLevelOrder"])
    with tempfile.TemporaryDirectory() as tmp:
        app = Path(tmp) / "app"
        shutil.copytree(ROOT / "app", app)
        data_template = app / ".ironflock" / "data-template.yml"
        undeclared = data_template.read_text(encoding="utf-8")
        declared = undeclared + "privileged:\n  reason: Reads the PLC over the serial port /dev/ttyUSB0\n"

        def findings(compose: dict | None, template: str, name: str) -> list[tuple[str, str, str]]:
            data_template.write_text(template, encoding="utf-8")
            compose_file = app / "docker-compose.yml"
            compose_file.unlink(missing_ok=True)
            if compose is not None:
                compose_file.write_text(json.dumps(compose, indent=2), encoding="utf-8")
            return validate(app, name)

        merge = "a release carries only docker-compose.yml"
        for case in fixture["cases"]:
            name, features = case["name"], case["features"]
            got = compose_privileges.classify(case["compose"])
            if got != features:
                problems.append(f"{name}: classify() gave {got}")

            def wanted(features: list[dict]) -> list[tuple[str, str]]:
                """(text, message part) for the ERROR each feature must get."""
                return [
                    (
                        (f'service "{f["service"]}": ' if f["service"] else "") + f"{f['feature']} {f['value']} ",
                        merge if f["feature"] in ("include", "extends") else "declare privileged.reason",
                    )
                    for f in features
                ]

            def missing(found: list[tuple[str, str, str]], wanted: list[tuple[str, str]]) -> bool:
                return len(found) != len(wanted) or any(
                    not any(lvl == "ERROR" and text in msg and part in msg for lvl, _, msg in found) for text, part in wanted
                )

            found = findings(case["compose"], undeclared, name)
            if missing(found, wanted(features)):
                problems.append(f"{name}, undeclared: expected an ERROR for each of {wanted(features)}, got {found}")
            found = findings(case["compose"], declared, name)
            other_files = wanted([f for f in features if f["feature"] in ("include", "extends")])
            if features and missing(found, other_files):
                problems.append(f"{name}, declared: expected an ERROR only for each of {other_files}, got {found}")
            if not features and [(lvl, path) for lvl, path, _ in found] != [("ERROR", "privileged")]:
                problems.append(f"{name}, declared without privileged settings: expected one ERROR at privileged, got {found}")

        # A single-image app may declare it (full access to the device) or not.
        for template, label in ((undeclared, "undeclared"), (declared, "declared")):
            if found := findings(None, template, f"single image, {label}"):
                problems.append(f"single image, {label}: expected no findings, got {found}")
        # The schema requires a reason with text in it.
        blank = undeclared + 'privileged:\n  reason: "  "\n'
        if [(lvl, path) for lvl, path, _ in findings(None, blank, "blank reason")] != [("ERROR", "privileged.reason")]:
            problems.append("a blank privileged.reason is not reported")
    return len(fixture["cases"]), problems


def check_classifier_shapes(compose_privileges, top_level_order: list[str]) -> list[str]:
    """The cases the fixture leaves out, with the same vectors as the platform's and the device agent's tests."""
    problems = []
    # No fixture case has every top-level section; one compose with all of
    # them, written in reverse, reports them in topLevelOrder.
    compose = {
        "include": ["other.yml"],
        "configs": {"c": {"file": "/etc/c"}},
        "secrets": {"s": {"file": "/etc/s"}},
        "networks": {"n": {"external": True}},
        "volumes": {"v": {"external": True}},
    }
    section = {
        "volume_external": "volumes",
        "network_external": "networks",
        "secret_file": "secrets",
        "config_file": "configs",
        "include": "include",
    }
    order = [section[f["feature"]] for f in compose_privileges.classify(compose)]
    if order != top_level_order:
        problems.append(f"top-level sections come in the order {order}, not the fixture's topLevelOrder")

    # null and "" are unset; any mapping or list is a truthy external or name;
    # non-strings are JSON-encoded (compactly, as the platform does).
    compose = {
        "include": {"path": ["a.yml", "b.yml"]},
        "services": {
            "app": {"cgroup_parent": None, "extends": "base", "ipc": {"mode": "$<x>"}},
            "web": {"cgroup_parent": False, "extends": {"file": 7, "service": "x"}},
        },
        "networks": {
            "a": {"external": {}},
            "b": {"driver": None, "driver_opts": {}, "external": 0, "name": ""},
            "c": {"driver": "", "name": []},
            "d": None,
        },
    }
    expected = [
        {"service": "app", "feature": "ipc", "value": '{"mode":"$<x>"}'},
        {"service": "web", "feature": "cgroup_parent", "value": "false"},
        {"service": "", "feature": "network_external", "value": "a"},
        {"service": "", "feature": "network_external", "value": "c"},
        {"service": "", "feature": "include", "value": '["a.yml","b.yml"]'},
    ]
    for compose, want in (
        (compose, expected),
        ({"include": None, "services": {}}, []),
        ({"include": [{}]}, [{"service": "", "feature": "include", "value": "null"}]),  # no path: JSON null
    ):
        if (got := compose_privileges.classify(compose)) != want:
            problems.append(f"classify({compose}) gave {got}, expected {want}")
    return problems


def main() -> int:
    failed = 0
    for board in [EXAMPLE, *sorted((ROOT / "boards").glob("*.yml"))]:
        found = run_board(board)
        expected = [m.groups() for m in map(EXPECT.match, board.read_text().splitlines()) if m]
        if board == EXAMPLE:
            problems = [f"unexpected {lvl} {path}: {msg}" for lvl, path, msg in found]
        else:
            problems = [
                f"missing {lvl} {path} :: {text}"
                for lvl, path, text in expected
                if not any(f[0] == lvl and f[1] == path and text in f[2] for f in found)
            ]
            clean = [m[1] for m in map(EXPECT_NONE.match, board.read_text().splitlines()) if m]
            problems += [f"unexpected {lvl} {path}: {msg}" for lvl, path, msg in found if path in clean]
        status = "ok  " if not problems else "FAIL"
        print(f"{status} {board.name}: {len(found)} finding(s), {len(expected)} expected")
        for problem in problems:
            print(f"     {problem}")
        failed += bool(problems)
    problems = check_starter()
    print(f"{'ok  ' if not problems else 'FAIL'} starter app and new_app.py")
    for problem in problems:
        print(f"     {problem}")
    failed += bool(problems)
    cases, problems = check_privileged()
    print(f"{'ok  ' if not problems else 'FAIL'} privileged access: {cases} compose case(s)")
    for problem in problems:
        print(f"     {problem}")
    failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
