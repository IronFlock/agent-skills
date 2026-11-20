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

Then app skills: the starter app's skill must pass, every mutation in
SKILL_MUTATIONS plants one mistake the release build refuses (or one the
validator warns about) into a copy of the starter, and validate.py must report
it; every case in SKILL_ACCEPTED is correct, at the limits, and must produce no
findings.

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
from typing import Callable

ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parent / "plugins/ironflock-dev/skills/ironflock-templates"
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


# -- app skills ----------------------------------------------------------------

MD_SKILL = ".ironflock/skills/machine-diagnosis"  # the starter's skill, relative to the app
SKILL_MD = f"{MD_SKILL}/SKILL.md"
AI = ".ironflock/ai-template.yml"


def edit(app: Path, relative: str, change: Callable[[str], str]) -> None:
    path = app / relative
    text = path.read_text(encoding="utf-8")
    changed = change(text)
    if changed == text:
        sys.exit(f"the mutation of {relative} changed nothing; the starter changed, update the test")
    path.write_text(changed, encoding="utf-8")


def write(app: Path, relative: str, content: str | bytes) -> None:
    path = app / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def skill(name: str, description: str = "Use it when the test needs it.", body: str = "Do the thing.") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def list_skills(*names: str) -> Callable[[str], str]:
    return lambda t: t.replace("skills: [machine-diagnosis]", f"skills: [{', '.join(names)}]")


def extra_skills(app: Path, count: int, listed: bool = True) -> None:
    """count more skills, each listed by the starter's agent when listed."""
    names = [f"extra-{i}" for i in range(count)]
    for name in names:
        write(app, f".ironflock/skills/{name}/SKILL.md", skill(name))
    if listed:
        edit(app, AI, list_skills("machine-diagnosis", *names))


def sub_agent(app: Path) -> None:
    """A second agent that lists a skill of its own, reached by delegation."""
    write(app, ".ironflock/skills/fault-codes/SKILL.md", skill("fault-codes"))
    edit(app, AI, lambda t: t.replace("  tools:\n", "  tools:\n    codes:\n      delegate: codes\n      description: Looks up fault codes.\n", 1)
         + "codes:\n  system_prompt: Look up fault codes with app/fault-codes.\n  skills: [fault-codes]\n"
         "  tools:\n    current_reading:\n      topic: current_reading\n      description: Reads the machine.\n"
         "  max_context_tokens: 8000\n  messages_after_summary: 5\n  max_iterations: 5\n")


def at_the_limits(app: Path) -> None:
    """Every limit reached, none exceeded."""
    write(app, ".ironflock/skills/limits/SKILL.md", skill("limits", "d" * 500, "i" * 20_000))
    for i in range(19):
        write(app, f".ironflock/skills/limits/references/r{i:02}.md", "r" * 40_000)
    write(app, ".ironflock/skills/limits/references/" + "n" * 61 + ".md", "x")  # the 20th, a 64-character name
    write(app, ".ironflock/skills/" + "a" * 64 + "/SKILL.md", skill("a" * 64))
    edit(app, AI, list_skills("machine-diagnosis", "limits", "a" * 64))


# name: (mutation, [(level, file, path, part of the message)])
SkillMutation = Callable[[Path], None]
SKILL_MUTATIONS: dict[str, tuple[SkillMutation, list[tuple[str, str, str, str]]]] = {
    # -- the agents' lists and tools ---------------------------------------
    "skill folder listed by no agent": (
        lambda a: edit(a, AI, lambda t: t.replace("  skills: [machine-diagnosis]\n", "")),
        [("ERROR", "skills/machine-diagnosis", "(root)", "no agent lists this skill")],
    ),
    "listed skill without a folder": (
        lambda a: edit(a, AI, list_skills("machine-diagnosis", "maintenance-playbook")),
        [("ERROR", "ai-template.yml", "machines.skills[1]", "no skill folder .ironflock/skills/maintenance-playbook/")],
    ),
    "skills folder without ai-template.yml": (
        lambda a: (a / AI).unlink(),
        [("ERROR", "skills", "(root)", "there is no ai-template.yml")],
    ),
    "app/ prefix in the list": (
        lambda a: edit(a, AI, list_skills("app/machine-diagnosis")),
        [("ERROR", "ai-template.yml", "machines.skills[0]", "without 'app/'")],
    ),
    "project/ prefix in the list": (
        lambda a: edit(a, AI, list_skills("machine-diagnosis", "project/notes")),
        [("ERROR", "ai-template.yml", "machines.skills[1]", "project skill")],
    ),
    "platform skill that is not open to apps": (
        lambda a: edit(a, AI, list_skills("machine-diagnosis", "platform/board-design")),
        [("ERROR", "ai-template.yml", "machines.skills[1]", "not a platform skill that apps can use")],
    ),
    "skill listed twice": (
        lambda a: edit(a, AI, list_skills("machine-diagnosis", "machine-diagnosis")),
        [("ERROR", "ai-template.yml", "machines.skills[1]", "listed twice")],
    ),
    "agent lists more than 20 skills": (
        lambda a: extra_skills(a, 20),
        [("ERROR", "ai-template.yml", "machines.skills", "lists 21 skills, at most 20")],
    ),
    "tool named load_skill": (
        lambda a: edit(a, AI, lambda t: t.replace("    current_reading:\n", "    load_skill:\n", 1)),
        [("ERROR", "ai-template.yml", "machines.tools.load_skill", "reserved")],
    ),
    # -- files ---------------------------------------------------------------
    "a script in the skill": (
        lambda a: write(a, f"{MD_SKILL}/check.sh", "#!/bin/sh\n"),
        [("ERROR", "skills/machine-diagnosis/check.sh", "(root)", "not allowed")],
    ),
    "a folder inside references": (
        lambda a: write(a, f"{MD_SKILL}/references/codes/list.md", "Codes."),
        [("ERROR", "skills/machine-diagnosis/references/codes/list.md", "(root)", "not allowed")],
    ),
    "reference file that is not markdown": (
        lambda a: write(a, f"{MD_SKILL}/references/codes.txt", "Codes."),
        [("ERROR", "skills/machine-diagnosis/references/codes.txt", "(root)", "<name>.md")],
    ),
    "reference file name over 64 characters": (
        lambda a: write(a, f"{MD_SKILL}/references/{'n' * 62}.md", "Codes."),
        [("ERROR", f"skills/machine-diagnosis/references/{'n' * 62}.md", "(root)", "65 characters, at most 64")],
    ),
    "file outside a skill folder": (
        lambda a: write(a, ".ironflock/skills/README.md", "Skills."),
        [("ERROR", "skills/README.md", "(root)", "not inside a skill folder")],
    ),
    "file that is not UTF-8": (
        lambda a: write(a, f"{MD_SKILL}/references/codes.md", "Temperatur in \u00b0C".encode("latin-1")),
        [("ERROR", "skills/machine-diagnosis/references/codes.md", "(root)", "not valid UTF-8")],
    ),
    "symbolic link": (
        lambda a: (a / MD_SKILL / "references").mkdir() or (a / MD_SKILL / "references/codes.md").symlink_to("../SKILL.md"),
        [("ERROR", "skills/machine-diagnosis/references/codes.md", "(root)", "symbolic link")],
    ),
    "skills folder is a symbolic link": (
        lambda a: [(a / ".ironflock/skills").rename(a / "skills"), (a / ".ironflock/skills").symlink_to("../skills")],
        [("ERROR", "skills", "(root)", "symbolic link")],
    ),
    "folder name not in the name pattern": (
        lambda a: write(a, ".ironflock/skills/Fault_Codes/SKILL.md", skill("Fault_Codes")),
        [("ERROR", "skills/Fault_Codes", "(root)", "lowercase letters and digits")],
    ),
    "folder name over 64 characters": (
        lambda a: write(a, f".ironflock/skills/{'a' * 65}/SKILL.md", skill("a" * 65))
        or edit(a, AI, list_skills("machine-diagnosis", "a" * 65)),
        [("ERROR", f"skills/{'a' * 65}", "(root)", "at most 64 characters")],
    ),
    "more than 20 skills": (
        lambda a: extra_skills(a, 20, listed=False),
        [("ERROR", "skills", "(root)", "the app has 21 skills, at most 20")],
    ),
    "skill files over 2 MiB together": (
        # 18 references of 40,000 three-byte characters: 2,160,000 bytes.
        lambda a: [write(a, f"{MD_SKILL}/references/r{i:02}.md", "\u20ac" * 40_000) for i in range(18)],
        [("ERROR", "skills", "(root)", "at most 2097152 (2 MiB)")],
    ),
    "hidden file": (
        lambda a: write(a, f"{MD_SKILL}/.DS_Store", b"\x00\x01"),
        [("WARN", "skills/machine-diagnosis/.DS_Store", "(root)", "if it is committed, the release build fails")],
    ),
    # -- SKILL.md -------------------------------------------------------------
    "skill folder without SKILL.md": (
        lambda a: write(a, ".ironflock/skills/fault-codes/references/codes.md", "Codes.")
        or edit(a, AI, list_skills("machine-diagnosis", "fault-codes")),
        [("ERROR", "skills/fault-codes", "(root)", "has no SKILL.md")],
    ),
    "no frontmatter": (
        lambda a: write(a, SKILL_MD, "# Diagnosing a machine\n\nDo the thing.\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "(root)", "must start with a '---' line")],
    ),
    "frontmatter not closed": (
        lambda a: write(a, SKILL_MD, "---\nname: machine-diagnosis\ndescription: x\n\nDo the thing.\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "(root)", "no closing '---'")],
    ),
    "frontmatter not valid YAML": (
        lambda a: write(a, SKILL_MD, "---\nname: machine-diagnosis\ndescription: [unclosed\n---\n\nDo the thing.\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "(root)", "not valid YAML")],
    ),
    "name differs from the folder": (
        lambda a: edit(a, SKILL_MD, lambda t: t.replace("name: machine-diagnosis", "name: diagnosis", 1)),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "name", "differs from the folder's name")],
    ),
    "no description": (
        lambda a: write(a, SKILL_MD, "---\nname: machine-diagnosis\n---\n\nDo the thing.\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "description", "needs `description`")],
    ),
    "description over 500 characters": (
        lambda a: write(a, SKILL_MD, skill("machine-diagnosis", "d" * 501)),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "description", "501 characters, at most 500")],
    ),
    "invisible character in the description": (
        lambda a: write(a, SKILL_MD, skill("machine-diagnosis", "Use it\u200b when a machine is hot.")),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "description", "U+200B")],
    ),
    "no instructions": (
        lambda a: write(a, SKILL_MD, "---\nname: machine-diagnosis\ndescription: Use it when a machine is hot.\n---\n\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "instructions", "no instructions")],
    ),
    "instructions over 20,000 characters": (
        lambda a: write(a, SKILL_MD, skill("machine-diagnosis", body="i" * 20_001)),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "instructions", "20001 characters, at most 20000")],
    ),
    "skill tag in the instructions": (
        lambda a: edit(a, SKILL_MD, lambda t: t + "\n</skill>\n"),
        [("ERROR", "skills/machine-diagnosis/SKILL.md", "instructions", "<skill> tag")],
    ),
    # -- references -----------------------------------------------------------
    "more than 20 reference files": (
        lambda a: [write(a, f"{MD_SKILL}/references/r{i:02}.md", "Codes.") for i in range(21)],
        [("ERROR", "skills/machine-diagnosis/references", "(root)", "21 reference files, at most 20")],
    ),
    "reference file over 40,000 characters": (
        lambda a: write(a, f"{MD_SKILL}/references/codes.md", "r" * 40_001),
        [("ERROR", "skills/machine-diagnosis/references/codes.md", "(root)", "40001 characters, at most 40000")],
    ),
    "empty reference file": (
        lambda a: write(a, f"{MD_SKILL}/references/codes.md", "\n"),
        [("ERROR", "skills/machine-diagnosis/references/codes.md", "(root)", "is empty")],
    ),
    # -- prompt text --------------------------------------------------------------
    "prompt names the skill without app/": (
        lambda a: edit(a, AI, lambda t: t.replace("skill app/machine-diagnosis", "skill machine-diagnosis")),
        [("WARN", "ai-template.yml", "machines.system_prompt", "offered it as app/machine-diagnosis")],
    ),
    "prompt names a skill the agent does not list": (
        lambda a: edit(a, AI, lambda t: t.replace("skill app/machine-diagnosis", "skill app/fault-codes")),
        [("WARN", "ai-template.yml", "machines.system_prompt", "does not list fault-codes")],
    ),
}

# name: a change to the starter that is correct, so validate.py must report
# nothing (a positive control for each limit and for what the build accepts).
SKILL_ACCEPTED: dict[str, SkillMutation] = {
    "every limit reached, none exceeded": at_the_limits,
    "20 skills, each listed": lambda a: extra_skills(a, 19),
    "a byte-order mark before the frontmatter": lambda a: edit(a, SKILL_MD, lambda t: "\ufeff" + t),
    "a reference file": lambda a: write(a, f"{MD_SKILL}/references/fault-codes_v2.md", "# Fault codes\n\nE1: sensor open.\n"),
    "a skill listed only by a sub-agent": sub_agent,
}


def skill_findings(app: Path, name: str) -> list[tuple[str, str, str, str]]:
    """(level, file, path, message) for every finding; the line is cut off the file."""
    done = subprocess.run([sys.executable, str(VALIDATE), str(app), "--offline"], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        sys.exit(f"validate.py crashed on {name}:\n{done.stdout}{done.stderr}")
    return [(m[1], m[2].rsplit(":", 1)[0] if re.search(r":\d+$", m[2]) else m[2], m[3], m[4])
            for m in map(FINDING.match, done.stdout.splitlines()) if m]


def check_skills() -> tuple[int, list[str]]:
    """Problems with validate.py's app-skill checks."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        shutil.copytree(STARTER, base, ignore=shutil.ignore_patterns("__pycache__"))
        (base / ".ironflock/board-template.yml").unlink()  # offline: no widget schemas needed
        if found := skill_findings(base, "the starter without its board"):
            return 0, [f"the base case is not clean: {found}"]
        cases = 0
        for name, (mutate, expected) in SKILL_MUTATIONS.items():
            app = Path(tmp) / f"case-{cases}"
            cases += 1
            shutil.copytree(base, app, symlinks=True)
            mutate(app)
            found = skill_findings(app, name)
            for level, file, path, text in expected:
                if not any(f[0] == level and f[1] == file and f[2] == path and text in f[3] for f in found):
                    problems.append(f"{name}: missing {level} {file} {path} :: {text}; got {found}")
        for name, mutate in SKILL_ACCEPTED.items():
            app = Path(tmp) / f"case-{cases}"
            cases += 1
            shutil.copytree(base, app, symlinks=True)
            mutate(app)
            if found := skill_findings(app, name):
                problems.append(f"{name}: expected no findings, got {found}")
    return cases, problems


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
    cases, problems = check_skills()
    print(f"{'ok  ' if not problems else 'FAIL'} app skills: {cases} case(s)")
    for problem in problems:
        print(f"     {problem}")
    failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
