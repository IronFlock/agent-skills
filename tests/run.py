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

Needs network access for the widget schemas (cached after the first run).
"""

from __future__ import annotations

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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
