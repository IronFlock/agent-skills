#!/usr/bin/env python3
"""Regression tests for the repository's own checks.

    python3 tests/repo_checks.py

1. tools/check_tools.py: a skill whose metadata.mcp-tools lists only tools of
   the catalogue passes; each case below plants one mistake (a tool the
   catalogue lacks, a name that is not a tool name, an empty list, a tool
   named in the text but not listed, a skill of `ironflock` that uses tools
   without a valid min-api-version or with one newer than the catalogue) and
   must be reported. A tool named in a skill without the list, or in its
   assets, is not.
2. tools/release.py in a throwaway git repository: `check` passes on a
   consistent copy and reports a plugin whose version differs from VERSION, a
   version in a marketplace entry, a version without a changelog section and
   a badly formed results file. `ci` and `gate` refuse a release without an
   eval result for every skill changed since the last release tag, or
   without release notes in the changelog, and pass once they are there.
3. evals/run.py, the parts that need no claude: the host check refuses every
   address but a local test instance's; the placeholders file is written as a
   template, then refused until every key has a value, then fills the
   prompts; finished runs are skipped and unfinished ones found and reset;
   the graders' totals, costs and durations are read back; an init event
   that shows the skill to the run without it, misses it in the run with it,
   or lists a foreign MCP server is refused; the commands and environments
   load the plugins only with the skill and nothing personal.

Offline, standard library only.
"""

from __future__ import annotations

import importlib.util
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

_spec = importlib.util.spec_from_file_location("eval_run", REPO / "evals/run.py")
eval_run = sys.modules["eval_run"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_run)

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
    ("name without underscore", "ironflock", "metadata:\n  mcp-tools: ping\n  min-api-version: 2.0.0\n", "Call `ping`.", None),
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
    ("yaml list, known", "ironflock", "metadata:\n  mcp-tools:\n    - list_devices\n    - ping\n  min-api-version: \"2.0.0\"\nlicense: MIT\n", "Call `ping`.", None),
    ("no min-api-version in ironflock", "ironflock", "metadata:\n  mcp-tools: ping\n", "Call `ping`.", "states the lowest API version it needs"),
    ("min-api-version outside metadata", "ironflock", "min-api-version: 2.0.0\nmetadata:\n  mcp-tools: ping\n", "Call `ping`.", "states the lowest API version it needs"),
    ("min-api-version not a version", "ironflock", "metadata:\n  mcp-tools: ping\n  min-api-version: 2.0\n", "Call `ping`.", "'2.0' is not a version"),
    ("no min-api-version with none", "ironflock", "metadata:\n  mcp-tools: none\n", "Nothing.", None),
    ("no min-api-version in ironflock-dev", "ironflock-dev", LISTED, "Call `list_devices`.", None),
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
    # A skill cannot need an API newer than the vendored catalogue; the same
    # version passes.
    for minimum, expected in (("2.1.0", "is newer than the catalogue's API 2.0.1"), ("2.0.1", None)):
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "ironflock", "s", f"metadata:\n  mcp-tools: ping\n  min-api-version: {minimum}\n", "Call `ping`.")
            found = check_tools.check(root, CATALOGUE, "2.0.1")
        if expected is None and found:
            problems.append(f"min-api-version {minimum}: unexpected {found}")
        elif expected is not None and not any(expected in f for f in found):
            problems.append(f"min-api-version {minimum}: expected '{expected}', got {found}")
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


def init_event(**changes) -> dict:
    """A good init event of a with_skill templates run, changed by `changes`."""
    event = {
        "type": "system",
        "subtype": "init",
        "apiKeySource": "ANTHROPIC_API_KEY",
        "model": "claude-test",
        "plugins": [
            {"name": "ironflock-dev", "path": str(REPO / "plugins/ironflock-dev")},
            {"name": "ironflock", "path": str(REPO / "plugins/ironflock")},
            {"name": "cc-plugin-telemetry", "path": "builtin"},
        ],
        "skills": ["ironflock-dev:ironflock-templates", "ironflock:ironflock-fleet", "dataviz"],
        "mcp_servers": [],
    }
    event.update(changes)
    return event


def check_eval_runner() -> tuple[int, list[str]]:
    problems = []
    cases = 0
    r = eval_run
    suites = r.SUITES

    def expect(label: str, ok: object, got: object = "") -> None:
        nonlocal cases
        cases += 1
        if not ok:
            problems.append(f"{label}: got {got!r}")

    # The host of the eval instance.
    for url in ("http://localhost:8080", "https://127.0.0.1", "http://[::1]:3000", "https://api.studio.localhost", "https://api.ironflock.test"):
        expect(f"host {url} is local", r.host_problem(url, []) is None, r.host_problem(url, []))
    for url in ("https://api.ironflock.com", "https://localhost.example.com", "http://notlocalhost", "ftp://localhost", "localhost:8080"):
        expect(f"host {url} is refused", r.host_problem(url, []), "accepted")
    expect("--allow-host accepts a named host", r.host_problem("https://eval.lan/x", ["EVAL.lan"]) is None)
    expect("--allow-host names that host only", r.host_problem("https://other.lan", ["eval.lan"]))

    # Placeholders: template, then refused while empty, then filled in.
    instance = [suites["fleet"], suites["data"]]
    keys = r.placeholder_keys(instance)
    expect("placeholder keys of both suites", set(keys) == {"project", "device", "offline_device", "app", "quantity", "threshold"}, sorted(keys))
    with tempfile.TemporaryDirectory() as tmp:
        iteration = Path(tmp) / "it"
        values, stop = r.check_placeholders(instance, iteration, write=False)
        expect("no template on a dry run", stop and not (iteration / "placeholders.json").exists(), stop)
        values, stop = r.check_placeholders(instance, iteration, write=True)
        written = json.loads((iteration / "placeholders.json").read_text())
        expect("a missing placeholders.json becomes a template", stop and written == {k: "" for k in keys}, written)
        values, stop = r.check_placeholders(instance, iteration, write=True)
        expect("empty values are refused", stop and "no value for" in stop[0], stop)
        filled = {k: f"<{k}>" for k in keys}
        (iteration / "placeholders.json").write_text(json.dumps(dict(filled, threshold=" ")))
        values, stop = r.check_placeholders([suites["data"]], iteration, write=True)
        expect("a blank value is refused", stop and "threshold" in stop[0], stop)
        values, stop = r.check_placeholders([suites["fleet"]], iteration, write=True)
        expect("fleet does not need data's keys", not stop, stop)
        (iteration / "placeholders.json").write_text(json.dumps(filled))
        values, stop = r.check_placeholders(instance, iteration, write=True)
        prompts = [run.prompt for s in instance for run in r.plan(s, iteration, [], r.CONFIGS, values)]
        expect("the prompts are filled in", not stop and not any("{" in p for p in prompts) and any("<project>" in p for p in prompts), stop)
        expect("other suites need no placeholders", r.check_placeholders([suites["connect"]], iteration, write=True) == ({}, []))

    # Skip and resume.
    with tempfile.TemporaryDirectory() as tmp:
        iteration = Path(tmp)
        runs = r.plan(suites["templates"], iteration, ["overview-board", "new-app"], r.CONFIGS, {})
        expect("--only plans the named evals in both configs", [x.label for x in runs] == [
            "templates/overview-board/with_skill", "templates/overview-board/without_skill",
            "templates/new-app/with_skill", "templates/new-app/without_skill"], [x.label for x in runs])
        for run in runs:
            r.reset(run)
        finished = runs[0]
        (finished.dir / "TRANSCRIPT.jsonl").write_text("{}\n")
        expect("a finished run is skipped", r.to_run(runs, False) == runs[1:], [x.label for x in r.to_run(runs, False)])
        expect("--force runs it again", r.to_run(runs, True) == runs)
        unfinished = r.unfinished_dirs(iteration, suites["templates"])
        expect("unfinished run folders are found, finished ones not", sorted(unfinished) == sorted(x.dir for x in runs[1:]), unfinished)
        app = runs[1].cwd
        expect("the fixture is copied", (app / ".ironflock/data-template.yml").is_file() and (app / "main.py").is_file(), sorted(p.name for p in app.iterdir()))
        expect("a fixture-less eval starts in an empty app folder", runs[2].cwd.is_dir() and not any(runs[2].cwd.iterdir()))
        (app / "board.yml").write_text("left over")
        r.reset(runs[1])
        expect("reset starts from a fresh copy", not (app / "board.yml").exists() and (app / "main.py").is_file())
        expect("reset prepares the run's own configuration", (runs[1].state / "gitconfig").is_file() and (runs[1].state / "npmrc").read_text() == "")
        expect("conversational evals get the answers as a second turn", len(runs[2].turns) == 2 and len(runs[0].turns) == 1)

    # The graders' totals; cost and duration from the transcripts.
    outputs = {
        "templates": "overview-board  with_skill  9/9\nwith_skill: 31/31 = 100%\nwithout_skill: 24/31 = 77%\n",
        "widgets": "\nwith_skill: 26/26 (100%)\nwithout_skill: 24/26 (92%)\n",
    }
    expect("totals with '='", r.parse_totals(outputs["templates"]) == {"with_skill": (31, 31), "without_skill": (24, 31)}, r.parse_totals(outputs["templates"]))
    expect("totals with '('", r.parse_totals(outputs["widgets"]) == {"with_skill": (26, 26), "without_skill": (24, 26)}, r.parse_totals(outputs["widgets"]))
    expect("no totals in a grader's error", r.parse_totals("Traceback ...\nKeyError: 'x'\n") == {})
    with tempfile.TemporaryDirectory() as tmp:
        transcript = Path(tmp) / "TRANSCRIPT.jsonl"
        lines = [init_event(claude_code_version="2.1.0"), {"type": "result", "total_cost_usd": 1.25, "duration_ms": 60000},
                 init_event(model="claude-other"), {"type": "result", "total_cost_usd": 0.5, "duration_ms": 30000}]
        transcript.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
        stats = r.transcript_stats(transcript)
        expect("cost and duration summed over the turns", (round(stats["cost"], 2), stats["duration_ms"]) == (1.75, 90000), stats)
        expect("models and version from the init events", stats["models"] == {"claude-test", "claude-other"} and stats["versions"] == {"2.1.0"}, stats)

    # The init event of a run.
    templates, fleet, connect = suites["templates"], suites["fleet"], suites["connect"]
    expect("a good with_skill run", r.init_problems(init_event(), templates, "with_skill") == [], r.init_problems(init_event(), templates, "with_skill"))
    bare = init_event(plugins=[{"name": "cc-plugin-telemetry", "path": "builtin"}], skills=["dataviz"])
    expect("a good without_skill run", r.init_problems(bare, templates, "without_skill") == [], r.init_problems(bare, templates, "without_skill"))
    expect("with_skill without the skill", r.init_problems(bare, templates, "with_skill"))
    expect("without_skill that sees the plugin", r.init_problems(init_event(), templates, "without_skill"))
    leaked = dict(bare, skills=["dataviz", "ironflock-templates"])
    expect("without_skill that sees the skill as a user skill", r.init_problems(leaked, templates, "without_skill"))
    cached = init_event(plugins=init_event()["plugins"] + [{"name": "posthog", "path": "/home/x/.claude/plugins/cache/p/posthog/1.0"}])
    expect("an installed plugin", r.init_problems(cached, templates, "with_skill"))
    expect("a login instead of the API key", r.init_problems(init_event(apiKeySource="/login managed key"), templates, "with_skill"))
    server = {"name": "ironflock", "status": "connected"}
    fleet_ok = init_event(skills=["ironflock:ironflock-fleet"], mcp_servers=[server])
    expect("fleet with its server alone", r.init_problems(fleet_ok, fleet, "with_skill") == [], r.init_problems(fleet_ok, fleet, "with_skill"))
    expect("fleet with a second server", r.init_problems(dict(fleet_ok, mcp_servers=[server, {"name": "plugin:ironflock:ironflock", "status": "connected"}]), fleet, "with_skill"))
    expect("fleet whose server failed", r.init_problems(dict(fleet_ok, mcp_servers=[dict(server, status="failed")]), fleet, "with_skill"))
    expect("fleet without its server", r.init_problems(dict(fleet_ok, mcp_servers=[]), fleet, "with_skill"))
    expect("connect with any server", r.init_problems(dict(fleet_ok, skills=["ironflock:ironflock-connect"], mcp_servers=[server]), connect, "with_skill"))

    retry = {"type": "system", "subtype": "api_retry", "error_status": 401, "error": "authentication_failed"}
    expect("a refused key stops the runs", r.key_refused(retry))
    expect("an overloaded API is retried", r.key_refused(dict(retry, error_status=529, error="overloaded")) is None)

    # Commands and environments.
    with tempfile.TemporaryDirectory() as tmp:
        iteration = Path(tmp)

        def command(suite: str, config: str, turn: int = 0, name: str | None = None) -> list[str]:
            spec = next(s for s in suites[suite].evals["evals"] if name in (None, s["name"]))
            return r.claude_command("claude", r.Run(suites[suite], spec, config, iteration, "prompt"), turn, "sid", None)

        def flag(cmd: list[str], name: str) -> list[str]:
            return [cmd[i + 1] for i, a in enumerate(cmd) if a == name]

        with_cmd, without_cmd = command("templates", "with_skill"), command("templates", "without_skill")
        expect("with_skill loads both plugins from the checkout", flag(with_cmd, "--plugin-dir") == [str(REPO / "plugins/ironflock-dev"), str(REPO / "plugins/ironflock")], with_cmd)
        expect("without_skill loads no plugin", "--plugin-dir" not in without_cmd, without_cmd)
        expect("every run is strict about MCP and reads user settings only", all(
            "--strict-mcp-config" in c and flag(c, "--setting-sources") == ["user"] for c in (with_cmd, without_cmd, command("fleet", "with_skill"))))
        expect("the prompt follows -p", with_cmd[1:3] == ["-p", "prompt"], with_cmd[:3])
        fleet_cmd = command("fleet", "without_skill")
        expect("fleet: the eval's MCP configuration and every tool allowed", flag(fleet_cmd, "--mcp-config") == [str(REPO / "evals/fleet/mcp.json")] and flag(fleet_cmd, "--permission-mode") == ["bypassPermissions"], fleet_cmd)
        expect("templates: no bypassPermissions", flag(with_cmd, "--permission-mode") == ["acceptEdits"], with_cmd)
        widget_cmd = command("widgets", "without_skill")
        expect("widgets: told never to publish", "publish" in " ".join(flag(widget_cmd, "--append-system-prompt")) and "Bash(git push:*)" in " ".join(flag(widget_cmd, "--settings")), widget_cmd)
        cli_cmd = command("cli", "with_skill")
        cli_settings = json.loads(flag(cli_cmd, "--settings")[0])
        expect("cli: the settings of evals.json, default mode", "Bash(curl:*)" in cli_settings["permissions"]["deny"] and flag(cli_cmd, "--permission-mode") == ["default"], cli_cmd)
        second = command("templates", "with_skill", 1, "new-app")
        expect("the answers resume the session", flag(second, "--resume") == ["sid"] and "--session-id" not in second and second[2] == suites["templates"].evals["evals"][3]["answers"], second[:8])

        base = {"PATH": "/usr/bin", "HOME": "/home/x", "CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli", "ANTHROPIC_API_KEY": "k",
                "ANTHROPIC_MODEL": "m", "GH_TOKEN": "t", "NPM_TOKEN": "t", "IRONFLOCK_EVAL_API_URL": "http://localhost", "IRONFLOCK_EVAL_API_KEY": "e", "IRONFLOCK_API_KEY": "real"}
        spec = suites["connect"].evals["evals"][0]
        env = r.run_env(r.Run(suites["connect"], spec, "with_skill", iteration), base)
        gone = [k for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_MODEL", "GH_TOKEN", "NPM_TOKEN", "IRONFLOCK_EVAL_API_KEY", "IRONFLOCK_API_KEY") if k in env]
        expect("nothing personal in a run's environment", not gone, gone)
        expect("the API key and a configuration of the run's own", env.get("ANTHROPIC_API_KEY") == "k" and env["CLAUDE_CONFIG_DIR"].startswith(str(iteration / ".state")) and env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1", env)
        spec = suites["fleet"].evals["evals"][0]
        env = r.run_env(r.Run(suites["fleet"], spec, "with_skill", iteration), base)
        expect("fleet keeps the eval instance's variables only", env.get("IRONFLOCK_EVAL_API_KEY") == "e" and "IRONFLOCK_API_KEY" not in env, sorted(env))
        login = next(s for s in suites["cli"].evals["evals"] if s["name"] == "login")
        env = r.run_env(r.Run(suites["cli"], login, "with_skill", iteration), base)
        expect("cli: the stand-in first on the PATH, logged out for login", env["PATH"].startswith(str(REPO / "evals/cli/fixtures/bin")) and "IRONFLOCK_EVAL_LOGGED_IN" not in env, env["PATH"])
    return cases, problems


def main() -> int:
    failed = 0
    for label, run in (
        ("MCP tool names", check_tool_names),
        ("version, changelog and eval results", check_release),
        ("eval runner", check_eval_runner),
    ):
        cases, problems = run()
        print(f"{'ok  ' if not problems else 'FAIL'} {label}: {cases} case(s)")
        for problem in problems:
            print(f"     {problem}")
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
