#!/usr/bin/env python3
"""Check the MCP tool names the skills use against the API's tool catalogue.

    python3 tools/check_tools.py                  check every skill
    python3 tools/check_tools.py vendor [API_DIR] copy the catalogue of a release

The catalogue is the list of tools the IronFlock API service offers over MCP:
their names, descriptions and input schemas. It is vendored here as
tools/api/tools.json, with the API version it came from in
tools/api/api-version.txt, because CI of this repository cannot read the API
service's sources.

A skill names the MCP tools it uses in its SKILL.md front matter, under
`metadata`, separated by spaces or as a YAML list:

    metadata:
      mcp-tools: list_devices check_app_status get_app_logs

`mcp-tools: none` says that the skill uses no tool.

A skill of `ironflock` that uses tools also states the lowest version of the
API service it needs, under `metadata`:

    metadata:
      mcp-tools: list_devices
      min-api-version: 2.0.0

Every skill of the `ironflock` plugin (the operator skills) must have the list.
In `ironflock-dev` it is optional: its skills for building apps mostly name the
tools of the IronFlock assistant inside an app, some of which share their names
with MCP tools (`execute_sql`), so a list there would mix the two. The check
reports

- a skill of `ironflock` without the list, or whose front matter cannot be read;
- a skill of `ironflock` that lists tools without `min-api-version`, with one
  that is not a version (x.y.z), or with one newer than the vendored
  catalogue's API version (a skill cannot need an API that is not released);
- a listed name that is not in the catalogue (a tool that was renamed or
  removed, or a typo);
- in a skill with the list: a tool of the catalogue that its Markdown names but
  the list leaves out. A name counts as named in inline code (`get_app_logs`),
  anywhere in a fenced code block, as a call (get_app_logs(...)), and with an
  MCP prefix (mcp__<server>__get_app_logs); plain prose does not count. A
  prefixed name on an ironflock server that the catalogue lacks is reported too.

`vendor` fetches the tags of API_DIR (default ../api, a checkout of the API
service), reads its VERSION, takes docs/tools.json from that version's release
tag v<version>, not from the working tree, and writes it and the version here.
It refuses a version older than the one vendored.

Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOGUE = REPO / "tools/api/tools.json"
CATALOGUE_VERSION = REPO / "tools/api/api-version.txt"
# Plugins whose every skill must list its MCP tools.
REQUIRED_PLUGINS = {"ironflock"}
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MCP_TOOLS = re.compile(r"^(\s+)mcp-tools:(.*)$")
MIN_API = re.compile(r"^\s+min-api-version:(.*)$")
LIST_ITEM = re.compile(r"^\s+-\s*(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
PREFIXED = re.compile(r"\bmcp__([A-Za-z0-9_-]*?)__([A-Za-z0-9_-]+)")
NONE = "none"


class Unreadable(Exception):
    pass


def catalogue_names(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    names = {tool["name"] for tool in data["tools"]}
    if not names:
        raise ValueError(f"{path}: no tools")
    return names


def front_matter_lines(skill_md: Path) -> list[str]:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise Unreadable("no front matter (the first line must be ---)")
    for end, line in enumerate(lines[1:], 1):
        if line.rstrip() == "---":
            return lines[1:end]
    raise Unreadable("the front matter has no closing ---")


def unquote(value: str) -> str:
    return value.strip().strip("'\"")


def declared_tools(skill_md: Path) -> list[str] | None:
    """The names in metadata.mcp-tools ([] for `none`), or None without the key.

    Read line by line, not as YAML: Claude Code reads front matter leniently,
    and the descriptions of today's skills are not valid YAML."""
    lines = front_matter_lines(skill_md)
    in_metadata = False
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith((" ", "\t")):
            in_metadata = line.rstrip() == "metadata:"
            continue
        match = MCP_TOOLS.match(line)
        if not (in_metadata and match):
            continue
        value = match[2].split(" #")[0].strip()
        if value.startswith("[") and value.endswith("]"):
            names = [unquote(v) for v in value[1:-1].split(",")]
        elif value:
            names = unquote(value).split()
        else:
            names = []
            for item in lines[i + 1 :]:
                if len(item) - len(item.lstrip()) <= len(match[1]) and item.strip():
                    break
                m = LIST_ITEM.match(item)
                if m:
                    names.append(unquote(m[1]))
        names = [n for n in names if n]
        if names == [NONE]:
            return []
        if not names:
            raise Unreadable("metadata.mcp-tools is empty: list the tools, or write `none`")
        return names
    return None


def declared_min_api(skill_md: Path) -> str | None:
    """The value of metadata.min-api-version, or None without the key."""
    in_metadata = False
    for line in front_matter_lines(skill_md):
        if line.strip() and not line.startswith((" ", "\t")):
            in_metadata = line.rstrip() == "metadata:"
            continue
        match = MIN_API.match(line)
        if in_metadata and match:
            return unquote(match[1].split(" #")[0])
    return None


def skill_dirs(root: Path) -> list[Path]:
    return sorted(p.parent for p in root.glob("plugins/*/skills/*/SKILL.md"))


def mentions(text: str, names: set[str]) -> list[tuple[int, str, bool]]:
    """(line, name, known) for every tool named in a counted form."""
    found: list[tuple[int, str, bool]] = []
    word = {n: re.compile(rf"(?<![\w-]){re.escape(n)}(?![\w-])") for n in names}
    call = {n: re.compile(rf"(?<![\w-]){re.escape(n)}\(") for n in names}
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        hits = set()
        for n in names:
            if in_fence and word[n].search(line):
                hits.add(n)
            elif call[n].search(line):
                hits.add(n)
        for code in INLINE_CODE.findall(line):
            if code.strip() in names:
                hits.add(code.strip())
        for server, n in PREFIXED.findall(line):
            if n in names:
                hits.add(n)
            elif "ironflock" in server.lower():
                found.append((lineno, n, False))
        found += [(lineno, n, True) for n in sorted(hits)]
    return found


def check(root: Path, names: set[str], api_version: str | None = None) -> list[str]:
    """Findings for every skill under root/plugins, as 'path: message'.

    api_version, the vendored catalogue's version, bounds min-api-version."""
    findings: list[str] = []
    for skill in skill_dirs(root):
        rel = skill.relative_to(root)
        required = rel.parts[1] in REQUIRED_PLUGINS
        try:
            declared = declared_tools(skill / "SKILL.md")
        except Unreadable as err:
            if required or "mcp-tools" in str(err):
                findings.append(f"{rel}/SKILL.md: {err}")
            continue
        if declared is None:
            if required:
                findings.append(
                    f"{rel}/SKILL.md: a skill of the {rel.parts[1]} plugin lists its MCP tools in metadata.mcp-tools (or `none`)"
                )
            continue
        if required and declared:
            minimum = declared_min_api(skill / "SKILL.md")
            if minimum is None:
                findings.append(
                    f"{rel}/SKILL.md: a skill of the {rel.parts[1]} plugin that uses tools states the lowest API version it needs in metadata.min-api-version"
                )
            elif not VERSION.match(minimum):
                findings.append(f"{rel}/SKILL.md: metadata.min-api-version: '{minimum}' is not a version (x.y.z)")
            elif api_version and VERSION.match(api_version) and version_key(minimum) > version_key(api_version):
                findings.append(
                    f"{rel}/SKILL.md: metadata.min-api-version: {minimum} is newer than the catalogue's API {api_version}"
                )
        for name in declared:
            if name not in names:
                findings.append(f"{rel}/SKILL.md: metadata.mcp-tools: '{name}' is not in the API's tool catalogue")
        for md in sorted(skill.rglob("*.md")):
            if "assets" in md.relative_to(skill).parts:
                continue  # starter apps and templates are copied into other repositories
            where = md.relative_to(root)
            for lineno, name, known in mentions(md.read_text(encoding="utf-8"), names):
                if not known:
                    findings.append(f"{where}:{lineno}: names the tool '{name}', which is not in the API's tool catalogue")
                elif name not in declared:
                    findings.append(f"{where}:{lineno}: names the tool '{name}', which metadata.mcp-tools leaves out")
    return findings


def git(api_dir: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(api_dir), *args], capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(f"git {' '.join(args)} in {api_dir} failed: {done.stderr.strip()}")
    return done.stdout


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in VERSION.match(version).groups())


def key(version: str) -> tuple[int, ...]:
    m = VERSION.match(version)
    if not m:
        sys.exit(f"'{version}' is not a version (x.y.z)")
    return tuple(int(p) for p in m.groups())


def vendor(api_dir: Path, catalogue: Path = CATALOGUE, version_file: Path = CATALOGUE_VERSION) -> int:
    git(api_dir, "fetch", "--quiet", "--tags", "origin")
    version = (api_dir / "VERSION").read_text(encoding="utf-8").strip()
    key(version)
    if version_file.exists():
        current = version_file.read_text(encoding="utf-8").strip()
        if key(version) < key(current):
            sys.exit(f"refusing: {api_dir} is at API {version}, older than the vendored {current}; update that checkout")
    tag = f"v{version}"
    git(api_dir, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
    content = git(api_dir, "show", f"{tag}:docs/tools.json")
    data = json.loads(content)
    count = len({tool["name"] for tool in data["tools"]})
    catalogue.parent.mkdir(parents=True, exist_ok=True)
    catalogue.write_text(content, encoding="utf-8")
    version_file.write_text(version + "\n", encoding="utf-8")
    print(f"{catalogue.name}: {count} tools of API {version} ({tag})")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "vendor":
        return vendor(Path(argv[1] if len(argv) > 1 else REPO.parent / "api").resolve())
    if argv:
        sys.exit(__doc__)
    names = catalogue_names(CATALOGUE)
    version = CATALOGUE_VERSION.read_text(encoding="utf-8").strip()
    findings = check(REPO, names, version)
    for finding in findings:
        print(f"ERROR {finding}")
    print(f"{'ok  ' if not findings else 'FAIL'} MCP tool names: {len(skill_dirs(REPO))} skill(s), catalogue of API {version}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
