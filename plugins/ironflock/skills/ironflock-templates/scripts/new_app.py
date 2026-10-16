#!/usr/bin/env python3
"""Create a new IronFlock app from the skill's starter app.

    new_app.py tank-monitor                         → ./tank-monitor
    new_app.py tank-monitor --dest DIR              → DIR
    new_app.py tank-monitor --title "Tank Monitor"  → the name shown on the board

Copies assets/app-template: an edge program (main.py) that reads a machine
(simulated) on every device, keeps the device's state and readings in the app's
tables, applies the settings users save on the board, and serves a live view
that the board embeds through the device's remote-access tunnel; its Dockerfile;
and the .ironflock templates of all of it. The copy passes validate.py as is.
references/app-architecture.md explains how the parts fit together.

The name is the app's name in IronFlock. It goes into the board template, and
the title into the texts. Standard library only. Never overwrites: the
destination must not exist, be empty, or hold nothing but a .git folder.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "assets" / "app-template"
NAME = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
SKIP = {"__pycache__", ".venv"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", help="the app's name in IronFlock, e.g. tank-monitor")
    parser.add_argument("--dest", help="target folder (default: ./<name>)")
    parser.add_argument("--title", help="the name shown on the board and in the texts (default: from the name)")
    args = parser.parse_args()

    name = args.name.strip()
    if not NAME.match(name):
        print(
            f"error: {args.name!r} is not a valid app name: start with a lower-case letter, "
            "then up to 39 lower-case letters, digits, '-' or '_'",
            file=sys.stderr,
        )
        return 1
    title = (args.title or " ".join(word.capitalize() for word in re.split(r"[-_]", name))).strip()
    dest = Path(args.dest or name).resolve()
    if dest.exists() and (not dest.is_dir() or any(p.name != ".git" for p in dest.iterdir())):
        print(f"error: {dest} already exists and holds more than a .git folder", file=sys.stderr)
        return 1

    for source in sorted(TEMPLATE.rglob("*")):
        if source.is_dir() or SKIP.intersection(source.relative_to(TEMPLATE).parts):
            continue
        target = dest / source.relative_to(TEMPLATE)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        target.write_text(text.replace("app-starter", name).replace("App Starter", title), encoding="utf-8")
        shutil.copymode(source, target)

    print(f"Created the IronFlock app {name} in {dest}.")
    print(
        "\nNext:\n"
        "  1. Replace the simulated read_machine() in main.py with the real data source,\n"
        "     and adapt the tables, the board and the live view to what the app does.\n"
        "  2. Replace the TODO: texts in README.md (the app's description for its users)\n"
        "     and CLAUDE.md.\n"
        f"  3. python3 {SKILL / 'scripts' / 'validate.py'} {dest}\n"
        "  4. Push to the app's repository in IronFlock and run it on a device from the IDE."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
