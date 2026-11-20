#!/usr/bin/env python3
"""Regression tests for the repository's own checks.

    python3 tests/repo_checks.py

1. tools/check_tools.py: a skill whose metadata.mcp-tools lists only tools of
   the catalogue passes; each case below plants one mistake (a tool the
   catalogue lacks, a name that is not a tool name, an empty list, a tool
   named in the text but not listed) and must be reported. A tool named in a
   skill without the list, or in its assets, is not.
2. tools/release.py in a throwaway git repository: `check` passes on a
   consistent copy and reports a plugin whose version differs from VERSION, a
   version in a marketplace entry, a version without a changelog section and
   a badly formed results file. `ci` and `gate` refuse a release without an
   eval result for every skill changed since the last release tag, or
   without release notes in the changelog, and pass once they are there.

Offline, standard library only.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "tools"))
import check_tools  # noqa: E402

CATALOGUE = {"list_devices", "get_app_logs", "check_app_status", "ping"}
SKILL = """---
name: {name}
description: A test skill: it uses tools.
{meta}---

# Test

{body}
"""


def write_skill(root: Path, plugin: str, name: str, meta: str = "", body: str = "Nothing.") -> Path:
    skill = root / "plugins" / plugin / "skills" / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(SKILL.format(name=name, meta=meta, body=body))
    return skill


LISTED = "metadata:\n  mcp-tools: list_devices\n"
TOOL_CASES: list[tuple[str, str, str, str, str | None]] = [
    # label, plugin, metadata block, body, expected finding (None: no finding)
    ("listed tools", "ironflock-dev", "metadata:\n  mcp-tools: list_devices get_app_logs\n", "Call `list_devices`.", None),
    ("no list in ironflock-dev", "ironflock-dev", "", "Run `list_devices` and `execute_sql`.", None),
    ("no list in ironflock", "ironflock", "", "Nothing.", "lists its MCP tools in metadata.mcp-tools"),
    ("none in ironflock", "ironflock", "metadata:\n  mcp-tools: none\n", "Install another plugin.", None),
    ("none, but a tool named", "ironflock", "metadata:\n  mcp-tools: none\n", "Call `ping`.", "names the tool 'ping'"),
    ("unknown tool", "ironflock-dev", "metadata:\n  mcp-tools: list_devices get_device_log\n", "", "'get_device_log' is not in the API's tool catalogue"),
    ("not a name", "ironflock-dev", "metadata:\n  mcp-tools: List-Devices\n", "", "'List-Devices' is not in the API's tool catalogue"),
    ("name without underscore", "ironflock", "metadata:\n  mcp-tools: ping\n", "Call `ping`.", None),
    ("empty list", "ironflock-dev", "metadata:\n  mcp-tools:\n", "", "metadata.mcp-tools is empty"),
    ("unlisted in inline code", "ironflock-dev", LISTED, "Then `get_app_logs`.", "names the tool 'get_app_logs'"),
    ("unlisted in a code block", "ironflock-dev", LISTED, "```text\nthen get_app_logs with since=1h\n```", "names the tool 'get_app_logs'"),
    ("unlisted call", "ironflock-dev", LISTED, "Then get_app_logs(since=1h).", "names the tool 'get_app_logs'"),
    ("unlisted with a prefix", "ironflock-dev", LISTED, "Then mcp__ironflock__get_app_logs.", "names the tool 'get_app_logs'"),
    ("unknown with a prefix", "ironflock-dev", LISTED, "Then mcp__ironflock__get_app_log.", "'get_app_log', which is not in the API's"),
    ("plain prose", "ironflock-dev", LISTED, "Then read get_app_logs output.", None),
    ("quoted list", "ironflock-dev", "metadata:\n  mcp-tools: \"list_devices\"\n", "", None),
    ("flow list", "ironflock-dev", "metadata:\n  mcp-tools: [list_devices, get_app_log]\n", "", "'get_app_log' is not in"),
    ("yaml list", "ironflock-dev", "metadata:\n  mcp-tools:\n    - list_devices\n    - get_app_log\n", "", "'get_app_log' is not in"),
    ("yaml list, known", "ironflock", "metadata:\n  mcp-tools:\n    - list_devices\n    - ping\nlicense: MIT\n", "Call `ping`.", None),
    ("other key", "ironflock-dev", "metadata:\n  owner: list_devices\n", "Then `get_app_logs`.", None),
]


def run_tool_case(plugin: str, meta: str, body: str, raw: str | None = None) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill = write_skill(root, plugin, "s", meta, body)
        if raw is not None:
            (skill / "SKILL.md").write_text(raw)
        return check_tools.check(root, CATALOGUE)


def make_api(tmp: Path, version: str) -> tuple[Path, Path]:
    """An API repository at origin with a release tag, and a clone of it."""
    origin = tmp / "origin"
    git(tmp, "init", "--quiet", "--initial-branch=main", str(origin))
    (origin / "docs").mkdir()
    (origin / "docs/tools.json").write_text(json.dumps({"tools": [{"name": "ping"}]}))
    (origin / "VERSION").write_text(version + "\n")
    git(origin, "add", "-A")
    git(origin, "commit", "--quiet", "-m", "api")
    clone = tmp / "api"
    git(tmp, "clone", "--quiet", str(origin), str(clone))
    git(origin, "tag", f"v{version}")  # tagged after the clone: only a fetch brings it
    return origin, clone


def run_vendor(api: Path, target: Path) -> tuple[int, str]:
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import check_tools as c; from pathlib import Path as P; "
        "t = P(sys.argv[3]); c.vendor(P(sys.argv[2]), t / 'tools.json', t / 'api-version.txt')"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code, str(REPO / "tools"), str(api), str(target)], capture_output=True, text=True
    )
    return done.returncode, done.stdout + done.stderr


def check_tool_names() -> tuple[int, list[str]]:
    problems = []
    cases = 0
    for label, plugin, meta, body, expected in TOOL_CASES:
        cases += 1
        found = run_tool_case(plugin, meta, body)
        if expected is None and found:
            problems.append(f"{label}: unexpected {found}")
        elif expected is not None and not any(expected in f for f in found):
            problems.append(f"{label}: expected '{expected}', got {found}")
    # A closing --- with trailing spaces still ends the front matter.
    cases += 1
    raw = "---\nname: s\nmetadata:\n  mcp-tools: get_app_log\n---   \n\nBody.\n"
    found = run_tool_case("ironflock-dev", "", "", raw)
    if not any("'get_app_log' is not in" in f for f in found):
        problems.append(f"closing --- with spaces: expected the unknown tool, got {found}")
    # Front matter that cannot be read fails a skill that must have the list.
    cases += 1
    found = run_tool_case("ironflock", "", "", "---\nname: s\nmetadata:\n  mcp-tools: ping\n\nBody.\n")
    if not any("no closing ---" in f for f in found):
        problems.append(f"unreadable front matter: expected a finding, got {found}")
    cases += 1
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill = write_skill(root, "ironflock-dev", "s", LISTED)
        (skill / "assets/app").mkdir(parents=True)
        (skill / "assets/app/README.md").write_text("Uses `get_app_logs`.\n")
        (skill / "references").mkdir()
        (skill / "references/more.md").write_text("Also `check_app_status`.\n")
        found = check_tools.check(root, CATALOGUE)
        if len(found) != 1 or "references/more.md:1" not in found[0]:
            problems.append(f"assets and references: expected one finding in references/more.md, got {found}")
    # vendor: fetches the tags first, and refuses an older API.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, api = make_api(tmp_path, "2.1.0")
        target = tmp_path / "vendored"
        target.mkdir()
        (target / "api-version.txt").write_text("2.0.1\n")
        cases += 1
        code, out = run_vendor(api, target)
        if code != 0 or (target / "api-version.txt").read_text() != "2.1.0\n":
            problems.append(f"vendor after a new API release: exit {code}: {out}")
        (target / "api-version.txt").write_text("3.0.0\n")
        cases += 1
        code, out = run_vendor(api, target)
        if code == 0 or "older than the vendored 3.0.0" not in out:
            problems.append(f"vendor of an older API: expected a refusal, got exit {code}: {out}")
    # The real skills against the vendored catalogue.
    cases += 1
    found = check_tools.check(REPO, check_tools.catalogue_names(check_tools.CATALOGUE))
    problems += [f"this repository: {f}" for f in found]
    return cases, problems


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
    )


def release(repo: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run([sys.executable, "-I", str(repo / "tools/release.py"), *args], capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def make_repo(tmp: Path) -> Path:
    """A repository with two plugins, two skills, version 1.0.0, unreleased."""
    repo = tmp / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy(REPO / "tools/release.py", repo / "tools/release.py")
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "m", "plugins": [{"name": "a", "source": "./plugins/a"}, {"name": "b", "source": "./plugins/b"}]})
    )
    for plugin, skill in (("a", "alpha"), ("b", "beta")):
        (repo / f"plugins/{plugin}/.claude-plugin").mkdir(parents=True)
        (repo / f"plugins/{plugin}/.claude-plugin/plugin.json").write_text(json.dumps({"name": plugin, "version": "1.0.0"}))
        write_skill(repo, plugin, skill)
    (repo / "VERSION").write_text("1.0.0\n")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0 - 2026-01-01\n\n- First.\n")
    (repo / "evals/results").mkdir(parents=True)
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "start")
    return repo


def write_results(repo: Path, version: str, text: str) -> None:
    (repo / f"evals/results/{version}.md").write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", f"evals {version}")


def check_release() -> tuple[int, list[str]]:
    problems: list[str] = []
    cases = 0

    def expect(label: str, args: tuple[str, ...], repo: Path, ok: bool, text: str = "") -> None:
        nonlocal cases
        cases += 1
        code, out = release(repo, *args)
        if (code == 0) != ok or text not in out:
            problems.append(f"{label}: expected {'pass' if ok else 'refusal'} with '{text}', got exit {code}:\n{out}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(Path(tmp))
        expect("consistent repository", ("check",), repo, True)

        def mutated(label: str, change: Callable[[Path], None], text: str) -> None:
            with tempfile.TemporaryDirectory() as tmp2:
                copy = Path(tmp2) / "repo"
                shutil.copytree(repo, copy)
                change(copy)
                expect(label, ("check",), copy, False, text)

        mutated(
            "plugin version",
            lambda r: (r / "plugins/b/.claude-plugin/plugin.json").write_text(json.dumps({"name": "b", "version": "0.9.0"})),
            "plugins/b/.claude-plugin/plugin.json: version '0.9.0'",
        )
        mutated(
            "marketplace version",
            lambda r: (r / ".claude-plugin/marketplace.json").write_text(
                json.dumps({"name": "m", "plugins": [{"name": "a", "source": "./plugins/a", "version": "1.0.0"}]})
            ),
            "the entry 'a' sets a version",
        )
        mutated("changelog", lambda r: (r / "CHANGELOG.md").write_text("# Changelog\n"), "no section '## 1.0.0'")
        mutated("results name", lambda r: (r / "evals/results/1.0.md").write_text(""), "the name must be <x.y.z>.md")
        mutated(
            "results without a result",
            lambda r: (r / "evals/results/1.0.0.md").write_text("## alpha\n\nRan it.\n"),
            "'## alpha' has no line 'Result: ...'",
        )
        mutated(
            "results of an unknown skill",
            lambda r: (r / "evals/results/1.0.1.md").write_text("## gamma\n\nResult: 3/3\n"),
            "'## gamma' is not a skill",
        )

        # The first release: no tag yet, so every skill needs its result.
        expect("first release without results", ("ci",), repo, False, "run the evals of alpha, beta")
        write_results(repo, "1.0.0", "# Evals\n\n## alpha\n\nResult: 4/4 with the skill, 2/4 without.\n")
        expect("first release, beta missing", ("ci",), repo, False, "no section for beta")
        write_results(repo, "1.0.0", "## alpha\n\nResult: 4/4\n\n## beta\n\nResult: TODO\n")
        expect("first release, beta TODO", ("ci",), repo, False, "'## beta' has a TODO")
        write_results(repo, "1.0.0", "## alpha\n\nResult: 4/4\n\n## beta\n\nResult: 3/3\n")
        expect("first release", ("ci",), repo, True)
        git(repo, "tag", "v1.0.0")

        # The next release changes beta only: only beta needs a result.
        (repo / "plugins/b/skills/beta/SKILL.md").write_text("---\nname: beta\n---\n\nChanged.\n")
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- Beta.\n\n## 1.0.0 - 2026-01-01\n\n- First.\n")
        git(repo, "add", "-A")
        git(repo, "commit", "--quiet", "-m", "beta")
        git(repo, "update-ref", "refs/remotes/origin/main", "v1.0.0")
        expect("gate without results", ("gate", "patch"), repo, False, "run the evals of beta, changed since v1.0.0")
        write_results(repo, "1.0.1", "## beta\n\nResult: 3/3\n")
        expect("gate", ("gate", "patch"), repo, True, "release 1.0.1 (main has 1.0.0)")
        expect("gate for minor", ("gate", "minor"), repo, False, "evals/results/1.1.0.md is missing")
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n## 1.0.0 - 2026-01-01\n\n- First.\n")
        git(repo, "commit", "--quiet", "-am", "empty notes")
        expect("gate without notes", ("gate", "patch"), repo, False, "no section '## Unreleased' with content")
        git(repo, "reset", "--quiet", "--hard", "HEAD~1")

        # A skill deleted since the last release needs no eval, and the
        # results of that release may still name it.
        with tempfile.TemporaryDirectory() as tmp2:
            copy = Path(tmp2) / "repo"
            shutil.copytree(repo, copy)
            git(copy, "reset", "--quiet", "--hard", "v1.0.0")
            shutil.rmtree(copy / "plugins/b/skills/beta")
            (copy / "plugins/a/skills/alpha/SKILL.md").write_text("---\nname: alpha\n---\n\nChanged.\n")
            (copy / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- No beta.\n\n## 1.0.0 - 2026-01-01\n\n- First.\n")
            git(copy, "add", "-A")
            git(copy, "commit", "--quiet", "-m", "drop beta")
            write_results(copy, "1.0.1", "## alpha\n\nResult: 4/4\n")
            expect("deleted skill", ("gate", "patch"), copy, True)
            expect("results naming a deleted skill", ("check",), copy, True)

        # The release writes the version, and CI accepts the release commit.
        code, out = release(repo, "write", "1.0.1")
        if code != 0:
            problems.append(f"write: exit {code}: {out}")
        git(repo, "commit", "--quiet", "-am", "release m v1.0.1")
        expect("release commit", ("ci",), repo, True, "release 1.0.1")
        cases += 1
        if json.loads((repo / "plugins/a/.claude-plugin/plugin.json").read_text()).get("version") != "1.0.1":
            problems.append("write: plugins/a/.claude-plugin/plugin.json does not carry 1.0.1")
    return cases, problems


def main() -> int:
    failed = 0
    for label, run in (("MCP tool names", check_tool_names), ("version, changelog and eval results", check_release)):
        cases, problems = run()
        print(f"{'ok  ' if not problems else 'FAIL'} {label}: {cases} case(s)")
        for problem in problems:
            print(f"     {problem}")
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
