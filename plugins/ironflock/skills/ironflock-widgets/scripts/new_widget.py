#!/usr/bin/env python3
"""Create a new IronFlock widget repository from the skill's starter template.

    new_widget.py progress-bar                     → ./widget-progress-bar
    new_widget.py progress-bar --dest DIR          → DIR
    new_widget.py progress-bar --title "Progress"  → schema title "Progress Configuration"

Copies assets/widget-template and renames everything derived from the widget's
name: the npm package (@ironflock/widget-<name>), the files, the custom element
tag (widget-<name>-versionplaceholder), the class (Widget<Name>), the schema
title and the generated root type (<Title>Configuration). The copy builds as is;
the `TODO:` texts mark what has to be written for the new widget, and
check_widget.py reports every one that is left.

Standard library only. Never overwrites: the destination must not exist or be empty.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "widget-template"
NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
TEXT_SUFFIXES = {".json", ".ts", ".md", ".html", ".yml", ".yaml", ".sh", ".js", ".mjs", ""}


def type_name(title: str) -> str:
    """The identifier json-schema-to-typescript derives from a schema title
    (its toSafeString): invalid characters become word breaks, each word is
    capitalised, and the words are joined."""
    words = re.sub(r"(^\s*[^a-zA-Z_$])|([^a-zA-Z_$\d])", " ", title).split()
    name = "".join(w[:1].upper() + w[1:] for w in words)
    return name[:1].upper() + name[1:]


def substitutions(name: str, title: str) -> list[tuple[str, str]]:
    pascal = "".join(part.capitalize() for part in name.split("-"))
    return [
        # Longest first, so a shorter token never rewrites part of a longer one.
        ("StarterConfiguration", type_name(f"{title} Configuration")),
        ("Starter Configuration", f"{title} Configuration"),
        ("WidgetStarter", f"Widget{pascal}"),
        ("widget-starter", f"widget-{name}"),
        ('"starter"', f'"{name}"'),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", help="the widget's name, e.g. progress-bar (a widget- prefix is dropped)")
    parser.add_argument("--dest", help="target folder (default: ./widget-<name>)")
    parser.add_argument("--title", help="display name for the schema title (default: from the name)")
    args = parser.parse_args()

    name = args.name.strip().removeprefix("widget-")
    if not NAME.match(name):
        print(f"error: {args.name!r} is not a valid widget name: use lower-case words joined by '-'", file=sys.stderr)
        return 1
    title = (args.title or " ".join(part.capitalize() for part in name.split("-"))).strip()
    if not type_name(title):
        print(f"error: the title {title!r} gives no usable type name", file=sys.stderr)
        return 1
    dest = Path(args.dest or f"widget-{name}").resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        print(f"error: {dest} already exists and is not an empty folder", file=sys.stderr)
        return 1

    replacements = substitutions(name, title)
    for source in sorted(TEMPLATE.rglob("*")):
        if source.is_dir() or "node_modules" in source.parts or "dist" in source.parts:
            continue
        relative = source.relative_to(TEMPLATE).as_posix().replace("widget-starter", f"widget-{name}")
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in TEXT_SUFFIXES:
            text = source.read_text(encoding="utf-8")
            for old, new in replacements:
                text = text.replace(old, new)
            target.write_text(text, encoding="utf-8")
        else:
            shutil.copyfile(source, target)
        shutil.copymode(source, target)

    print(f"Created {dest} for @ironflock/widget-{name} (<widget-{name}-<version>>).")
    print(
        "\nNext:\n"
        f"  cd {dest}\n"
        "  git init -b main && npm install && npm run build\n"
        "  npm start                       # the demo on http://localhost:8000/demo/\n"
        "\nThen replace every TODO: (schema description and aiSelection, package.json\n"
        "description, README.md, CLAUDE.md), adapt the component, add thumbnail.png\n"
        "and thumbnail.webp, and run check_widget.py until it reports no errors.\n"
        "references/new-widget.md lists what the platform needs before the widget can\n"
        "be used on a board."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
