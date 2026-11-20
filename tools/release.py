#!/usr/bin/env python3
"""The repository's version, changelog and eval results, for `just test` and
the release.

    python3 tools/release.py check            the files agree (just test)
    python3 tools/release.py gate <level>     before a release (just release-<level>)
    python3 tools/release.py ci               in the release workflow
    python3 tools/release.py write <version>  writes the version (just _write-version)

One semantic version for the repository: VERSION, and the `version` of every
plugin the marketplace lists. A release is the git tag v<version>.

CHANGELOG.md collects what changed under `## Unreleased`; the release turns
that heading into `## <version> - <date>`.

evals/results/<version>.md records the evals of a release: one section
`## <skill>` per skill, each with a line `Result: ...`. A release needs a
section for every skill whose files changed since the last release tag (every
skill, before the first one).

`check` makes sure VERSION is a version, every plugin carries it, the
marketplace entries carry none, the changelog has a section for it, and every
results file is well formed. `gate <level>` takes the version that
`just release-<level>` will make from VERSION on origin/main and refuses,
saying why, unless the commit (HEAD) has an `## Unreleased` section with
content and evals/results/<version>.md covers every changed skill. `ci` does
the same for the version in VERSION, whose changelog section is written by
then.

Standard library only; needs git.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO / "VERSION"
CHANGELOG = REPO / "CHANGELOG.md"
MARKETPLACE = REPO / ".claude-plugin/marketplace.json"
RESULTS = "evals/results"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")
SKILL_PATH = re.compile(r"^plugins/[^/]+/skills/([^/]+)/")
RESULT = re.compile(r"^Result:\s*(\S.*)$")


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout if done.returncode == 0 else ""


def key(version: str) -> tuple[int, int, int]:
    m = SEMVER.match(version)
    if not m:
        raise ValueError(f"'{version}' is not a version (x.y.z)")
    return int(m[1]), int(m[2]), int(m[3])


def next_version(level: str, version: str) -> str:
    major, minor, patch = key(version)
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "major":
        return f"{major + 1}.0.0"
    sys.exit(f"level must be patch, minor or major, got '{level}'")


def plugin_manifests(root: Path = REPO) -> list[Path]:
    """plugin.json of every plugin the marketplace lists from this repository."""
    entries = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))["plugins"]
    return [root / e["source"] / ".claude-plugin/plugin.json" for e in entries if isinstance(e.get("source"), str)]


def skill_names(root: Path = REPO) -> set[str]:
    return {p.parent.name for p in root.glob("plugins/*/skills/*/SKILL.md")}


def sections(text: str, level: str = "## ") -> dict[str, list[str]]:
    """Markdown sections at one heading level: heading text -> its lines."""
    out: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith(level):
            current = line[len(level) :].strip()
            out[current] = []
        elif line.startswith("# "):
            current = None
        elif current is not None:
            out[current].append(line)
    return out


def changelog_section(text: str, version: str) -> list[str] | None:
    for heading, lines in sections(text).items():
        if heading == version or heading.startswith(version + " "):
            return lines
    return None


def has_content(lines: list[str] | None) -> bool:
    return lines is not None and any(line.strip() for line in lines)


def results_findings(name: str, text: str, skills: set[str] | None) -> list[str]:
    """Problems of one evals/results file; name is its file name. Section names
    are checked against skills unless it is None (the results of a release made
    already may name a skill that was deleted since)."""
    findings = []
    if not SEMVER.match(name.removesuffix(".md")) or not name.endswith(".md"):
        findings.append(f"{RESULTS}/{name}: the name must be <x.y.z>.md")
    for skill, lines in sections(text).items():
        if skills is not None and skill not in skills:
            findings.append(f"{RESULTS}/{name}: '## {skill}' is not a skill of this repository")
        results = [m[1] for m in map(RESULT.match, lines) if m]
        if not results:
            findings.append(f"{RESULTS}/{name}: '## {skill}' has no line 'Result: ...'")
        elif any("TODO" in r for r in results):
            findings.append(f"{RESULTS}/{name}: '## {skill}' has a TODO for its result")
    return findings


def check(root: Path = REPO) -> list[str]:
    findings = []
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.match(version):
        return [f"VERSION: '{version}' is not a version (x.y.z)"]
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    for entry in marketplace["plugins"]:
        if "version" in entry:
            findings.append(
                f".claude-plugin/marketplace.json: the entry '{entry.get('name')}' sets a version; only plugin.json does"
            )
    for manifest in plugin_manifests(root):
        rel = manifest.relative_to(root)
        found = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        if found != version:
            findings.append(f"{rel}: version {found!r}, but VERSION is {version} (just _write-version {version})")
    changelog = root / "CHANGELOG.md"
    if not has_content(changelog_section(changelog.read_text(encoding="utf-8"), version)):
        findings.append(f"CHANGELOG.md: no section '## {version}' with content")
    skills = skill_names(root)
    for path in sorted((root / RESULTS).glob("*")):
        if path.name != ".gitkeep":
            older = SEMVER.match(path.stem) is not None and key(path.stem) <= key(version)
            findings += results_findings(path.name, path.read_text(encoding="utf-8"), None if older else skills)
    return findings


def last_release(below: str) -> str | None:
    """The highest release tag v<x.y.z> below the given version."""
    versions = [m[1] for m in map(TAG.match, git("tag", "--list", "v*").split()) if m]
    versions = [v for v in versions if key(v) < key(below)]
    return f"v{max(versions, key=key)}" if versions else None


def skills_at_head() -> set[str]:
    paths = git("ls-tree", "-r", "--name-only", "HEAD", "--", "plugins").split("\n")
    return {m[1] for m in map(SKILL_PATH.match, paths) if m and m[0] + "SKILL.md" == m.string}


def changed_skills(since: str | None) -> set[str]:
    """Skills of HEAD whose files changed since the tag (every skill without a
    tag). A skill that was deleted needs no eval."""
    skills = skills_at_head()
    if since is None:
        return skills
    paths = git("diff", "--name-only", since, "HEAD", "--", "plugins").split("\n")
    return {m[1] for m in map(SKILL_PATH.match, paths) if m} & skills


def at_head(path: str) -> str | None:
    done = subprocess.run(["git", "-C", str(REPO), "show", f"HEAD:{path}"], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def release_findings(version: str, changelog_heading: str) -> list[str]:
    findings = []
    changelog = at_head("CHANGELOG.md") or ""
    if not has_content(changelog_section(changelog, changelog_heading)):
        findings.append(
            f"CHANGELOG.md has no section '## {changelog_heading}' with content: write what changed for users, commit it"
        )
    since = last_release(version)
    changed = changed_skills(since)
    name = f"{version}.md"
    results = at_head(f"{RESULTS}/{name}")
    what = f"since {since}" if since else "(the first release: every skill)"
    if results is None:
        if changed:
            findings.append(
                f"{RESULTS}/{name} is missing: run the evals of {', '.join(sorted(changed))}, changed {what}, record them there, commit it"
            )
        return findings
    findings += results_findings(name, results, skill_names())
    missing = sorted(changed - set(sections(results)))
    if missing:
        findings.append(f"{RESULTS}/{name} has no section for {', '.join(missing)}, changed {what}")
    return findings


def write(version: str) -> None:
    key(version)
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")
    for manifest in plugin_manifests():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = version
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text = CHANGELOG.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()
    text = re.sub(r"(?m)^## Unreleased[ \t]*$", f"## {version} - {today}", text, count=1)
    CHANGELOG.write_text(text, encoding="utf-8")


def report(findings: list[str], what: str) -> int:
    for finding in findings:
        print(f"ERROR {finding}", file=sys.stderr)
    print(f"{'ok  ' if not findings else 'FAIL'} {what}")
    return 1 if findings else 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "check" and len(argv) == 1:
        return report(check(), "version, changelog and eval results")
    if cmd == "gate" and len(argv) == 2:
        base = git("show", "origin/main:VERSION", check=False).strip()
        if not base:
            sys.exit("release: VERSION has no version on origin/main (git fetch origin main)")
        version = next_version(argv[1], base)
        print(f"==> release {version} (main has {base})")
        return report(release_findings(version, "Unreleased"), f"release notes and evals for {version}")
    if cmd == "ci" and len(argv) == 1:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        key(version)
        return report(release_findings(version, version) + check(), f"release {version}")
    if cmd == "write" and len(argv) == 2:
        write(argv[1])
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
