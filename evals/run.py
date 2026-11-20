#!/usr/bin/env python3
"""Run the skill evals once with the skill and once without, grade them and
write SUMMARY.md.

    python3 evals/run.py all <iteration-dir>        every suite except cli
    python3 evals/run.py <suite> <iteration-dir>    templates, widgets, connect, fleet, data
    python3 evals/run.py cli <iteration-dir> --in-container

Options:
    --only <eval>         run only this eval (repeatable)
    --config with|without run only this configuration
    --force               run again what has run already
    --jobs N              runs at the same time (default 3)
    --model <model>       passed to claude (default: claude's own)
    --timeout <minutes>   per turn of a run (default 60)
    --allow-host <host>   fleet and data: also accept this host
    --dry-run             print the claude and grader commands, run nothing

Each suite runs in <iteration-dir>/<suite>/, in the layout its grader reads:
<eval>/<config>/ with config with_skill or without_skill. A run is finished
when its TRANSCRIPT.jsonl is there; the runner skips finished runs, so the
same command resumes an interrupted iteration. A run that did not finish is
started again from a fresh copy of its fixture.

Every run is `claude -p` in its own folder, with a configuration directory of
its own (no CLAUDE.md, memory, hooks, settings, plugins or MCP servers of the
person who runs it) and no npm, GitHub or git credentials. with_skill loads
the plugin of the skill from this checkout with --plugin-dir; without_skill
loads no plugin. The runner checks each run's init event for this and stops a
run that shows anything else. `claude --bare` is not used: it leaves the agent
only Bash, Edit and Read, no Skill tool and no skill list, so a skill could
not be used at all.

Evals run on demand (they cost model usage); a release does not need them.
To record a run, copy the sections SUMMARY.md lists into
evals/results/<version>.md and commit it (README.md, "Eval results, on
demand").

Needs ANTHROPIC_API_KEY; fleet and data also IRONFLOCK_EVAL_API_URL (a local
test instance) and IRONFLOCK_EVAL_API_KEY, and <iteration-dir>/placeholders.json.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent
PLUGINS = REPO / "plugins"
sys.path.insert(0, str(EVALS / "fleet"))
sys.path.insert(0, str(PLUGINS / "ironflock-dev/skills/ironflock-widgets/scripts"))
from check_widget import find_node_binary  # noqa: E402
from transcript import fill  # noqa: E402

# node and npm for the widget runs, as the widgets grader finds them (an nvm
# install when the shell has none on the PATH).
NODE = find_node_binary()

CONFIGS = ("with_skill", "without_skill")
FINISHED = "TRANSCRIPT.jsonl"
INSTANCE_VARS = ("IRONFLOCK_EVAL_API_URL", "IRONFLOCK_EVAL_API_KEY")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Environment variables a run never sees: credentials for npm and GitHub and
# the SSH agent. Everything that starts with CLAUDE is dropped too, and of
# ANTHROPIC_* only the key and the base URL are kept.
HIDDEN = {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "NPM_TOKEN", "NODE_AUTH_TOKEN", "SSH_AUTH_SOCK"}
# The agents of templates and widgets work in their folder with every command
# allowed, except those that publish or reach other machines.
DEV_SETTINGS = {
    "permissions": {
        "allow": ["Bash", "WebFetch", "WebSearch"],
        "deny": [
            "Bash(git push:*)", "Bash(npm publish:*)", "Bash(npm run release:*)", "Bash(yarn publish:*)",
            "Bash(pnpm publish:*)", "Bash(npm login:*)", "Bash(npm adduser:*)", "Bash(gh:*)",
            "Bash(docker push:*)", "Bash(sudo:*)", "Bash(ssh:*)", "Bash(scp:*)",
        ],
    }
}
NO_PUBLISH = "Never publish, release, commit or push anything."
MAX_FAILURES = 3


@dataclass(frozen=True)
class Suite:
    name: str
    evals_file: Path
    plugins: tuple[str, ...]  # plugin folders for with_skill
    workdir: str  # the agent's folder inside the run folder ("" = the run folder)
    reply: str  # the file the final reply is saved in
    grader: tuple[str, ...]  # arguments before the iteration folder
    mode: str  # --permission-mode
    settings: dict | None = None
    system: str = ""
    mcp: Path | None = None  # --mcp-config; the init event must list exactly its server

    @property
    def evals(self) -> dict:
        return json.loads(self.evals_file.read_text(encoding="utf-8"))

    @property
    def skill(self) -> str:
        return self.evals["skill_name"]


PY = sys.executable
SUITES = {
    s.name: s
    for s in (
        Suite("templates", EVALS / "evals.json", ("ironflock-dev", "ironflock"), "app", "REPLY.md",
              ("uv", "run", str(EVALS / "grade.py")), "acceptEdits", DEV_SETTINGS),
        Suite("widgets", EVALS / "widgets/evals.json", ("ironflock-dev", "ironflock"), "", "REPORT.md",
              (PY, str(EVALS / "widgets/grade.py"), "grade"), "acceptEdits", DEV_SETTINGS, NO_PUBLISH),
        Suite("connect", EVALS / "connect/evals.json", ("ironflock",), "work", "REPLY.md",
              (PY, str(EVALS / "connect/grade.py")), "acceptEdits"),
        Suite("fleet", EVALS / "fleet/evals.json", ("ironflock",), "", "REPLY.md",
              (PY, str(EVALS / "fleet/grade.py"), "grade"), "bypassPermissions", mcp=EVALS / "fleet/mcp.json"),
        Suite("data", EVALS / "data/evals.json", ("ironflock",), "", "REPLY.md",
              (PY, str(EVALS / "data/grade.py"), "grade"), "bypassPermissions", mcp=EVALS / "fleet/mcp.json"),
        Suite("cli", EVALS / "cli/evals.json", ("ironflock",), "work", "REPLY.md",
              (PY, str(EVALS / "cli/grade.py")), "default"),
    )
}
ALL = ("templates", "widgets", "connect", "fleet", "data")
INSTANCE_SUITES = ("fleet", "data")


@dataclass
class Run:
    suite: Suite
    spec: dict
    config: str
    iteration: Path
    prompt: str = ""

    @property
    def label(self) -> str:
        return f"{self.suite.name}/{self.spec['name']}/{self.config}"

    @property
    def dir(self) -> Path:
        return self.iteration / self.suite.name / self.spec["name"] / self.config

    @property
    def cwd(self) -> Path:
        return self.dir / self.suite.workdir if self.suite.workdir else self.dir

    @property
    def state(self) -> Path:
        """What the runner keeps apart from the agent: claude's configuration,
        the transcript while the run lasts, stderr."""
        return self.iteration / ".state" / self.suite.name / self.spec["name"] / self.config

    @property
    def turns(self) -> list[str]:
        """The prompt, and the answers of a conversational eval as the second turn."""
        return [self.prompt] + ([self.spec["answers"]] if self.spec.get("answers") else [])


# --- pure parts (tests/repo_checks.py) --------------------------------------


def host_problem(url: str, allowed: list[str]) -> str | None:
    """Why the address of the eval instance is refused, or None."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        return f"IRONFLOCK_EVAL_API_URL is not an http(s) address: {url!r}"
    if host in LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".test") or host in {h.lower() for h in allowed}:
        return None
    return (
        f"IRONFLOCK_EVAL_API_URL points at {host}, which is not a local test instance. "
        "The prompts ask for deletions. Use localhost, 127.0.0.1, a *.localhost or *.test host, "
        "or name the host with --allow-host if it is a test instance."
    )


def placeholder_keys(suites: list[Suite]) -> dict[str, list[str]]:
    """Each placeholder key with its descriptions, in the order of the suites."""
    keys: dict[str, list[str]] = {}
    for suite in suites:
        for key, text in suite.evals.get("placeholders", {}).items():
            keys.setdefault(key, []).append(f"{suite.name}: {text}")
    return keys


def missing_placeholders(values: dict, keys) -> list[str]:
    return [k for k in keys if not str(values.get(k, "")).strip()]


def is_finished(run_dir: Path) -> bool:
    return (run_dir / FINISHED).is_file()


def to_run(runs: list[Run], force: bool) -> list[Run]:
    return [r for r in runs if force or not is_finished(r.dir)]


def unfinished_dirs(iteration: Path, suite: Suite) -> list[Path]:
    """Run folders without a transcript: started and not finished, or set up
    and not started. The graders would score them as runs."""
    root = iteration / suite.name
    if not root.is_dir():
        return []
    return [d for e in sorted(root.iterdir()) if e.is_dir() for d in sorted(e.iterdir()) if d.name in CONFIGS and not is_finished(d)]


TOTAL = re.compile(r"^(with_skill|without_skill): (\d+)/(\d+)", re.M)


def parse_totals(output: str) -> dict[str, tuple[int, int]]:
    """The totals per configuration a grader prints last ("with_skill: 5/6 ...")."""
    return {m[1]: (int(m[2]), int(m[3])) for m in TOTAL.finditer(output)}


def events(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def transcript_stats(path: Path) -> dict:
    """Cost and duration summed over the result events, and the models and the
    Claude Code version of the init events."""
    stats = {"cost": 0.0, "duration_ms": 0, "models": set(), "versions": set()}
    for event in events(path):
        if event.get("type") == "result":
            stats["cost"] += float(event.get("total_cost_usd") or 0)
            stats["duration_ms"] += int(event.get("duration_ms") or 0)
        elif event.get("type") == "system" and event.get("subtype") == "init":
            if event.get("model"):
                stats["models"].add(str(event["model"]))
            if event.get("claude_code_version"):
                stats["versions"].add(str(event["claude_code_version"]))
    return stats


# What a run without the skill reaches for when it looks for the skill itself:
# this repository (GitHub, raw.githubusercontent.com, a clone), a skill folder
# of it, or the plugins installed in the home folder. Bash and the web are
# allowed, so this is found after the run, not prevented.
SKILL_SOURCE = re.compile(r"agent-skills|skills/ironflock-|(?:~|\$HOME|\$\{HOME\}|/(?:Users|home)/[^/\s\"']+)/\.claude\b", re.I)


def skill_lookups(transcript: Path) -> list[str]:
    """The tool calls of a run that reach for the skill's source, each as
    "<tool> <input>" (shortened)."""
    found = []
    for event in events(transcript):
        if event.get("type") != "assistant":
            continue
        for part in (event.get("message") or {}).get("content") or []:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                text = json.dumps(part.get("input"), ensure_ascii=False)
                if SKILL_SOURCE.search(text):
                    found.append(f"{part.get('name')} {text[:200]}")
    return found


def tainted_runs(iteration: Path, suite: str) -> dict[str, list[str]]:
    """The without_skill runs of a suite that reached for the skill, by eval."""
    tainted = {}
    for meta_file in sorted((iteration / suite).glob("*/without_skill/RUN.json")):
        lookups = json.loads(meta_file.read_text(encoding="utf-8")).get("skill_lookups") or []
        if lookups:
            tainted[meta_file.parent.parent.name] = lookups
    return tainted


def init_problems(event: dict, suite: Suite, config: str) -> list[str]:
    """What is wrong with a run's init event: anything the run may not see,
    or the plugin it must see missing."""
    problems = []
    if event.get("apiKeySource") != "ANTHROPIC_API_KEY":
        problems.append(f"authenticated with {event.get('apiKeySource')!r}, not ANTHROPIC_API_KEY")
    ours = {"ironflock", "ironflock-dev"}
    plugins = {str(p.get("name")) for p in event.get("plugins") or [] if isinstance(p, dict)}
    paths = [str(p.get("path", "")) for p in event.get("plugins") or [] if isinstance(p, dict)]
    skills = [str(s) for s in event.get("skills") or []]
    if config == "with_skill":
        expected = f"{suite.plugins[0]}:{suite.skill}"
        if expected not in skills:
            problems.append(f"the skill {expected} is not loaded")
        foreign = [p for p in paths if p.startswith("/") and not p.startswith(str(PLUGINS))]
        if foreign:
            problems.append(f"plugins from outside this checkout: {', '.join(foreign)}")
    else:
        leaked = sorted(plugins & ours) + [s for s in skills if s.split(":")[-1].startswith("ironflock")]
        if leaked:
            problems.append(f"the run without the skill sees {', '.join(leaked)}")
    installed = [p for p in paths if "/plugins/cache/" in p]
    if installed:
        problems.append(f"installed plugins are loaded: {', '.join(installed)}")
    servers = [s if isinstance(s, dict) else {"name": str(s)} for s in event.get("mcp_servers") or []]
    if suite.mcp:
        names = [str(s.get("name")) for s in servers]
        if names != ["ironflock"]:
            problems.append(f"MCP servers {names or 'none'}, expected only the eval's ironflock")
        elif servers[0].get("status") not in (None, "connected", "pending"):
            problems.append(f"the eval's ironflock server is {servers[0].get('status')}: is the local instance up and the key right?")
    elif servers:
        problems.append(f"MCP servers {[s.get('name') for s in servers]}, expected none")
    return problems


def key_refused(event: dict) -> str | None:
    """Why the API refuses every request, from a retry event; claude would
    otherwise retry for minutes and then report the refusal as its reply."""
    if event.get("type") == "system" and event.get("subtype") == "api_retry" and event.get("error_status") in (401, 402, 403):
        return f"the API refused the requests (HTTP {event['error_status']}, {event.get('error')}): check ANTHROPIC_API_KEY and its credit"
    return None


def cli_settings(evals: dict) -> dict:
    """The permission settings that evals/cli/evals.json gives in its setup text."""
    text = evals["setup"]
    return json.JSONDecoder().raw_decode(text[text.index('{"permissions"'):])[0]


def run_env(run: Run, base: dict[str, str]) -> dict[str, str]:
    """The environment of a run: base without anything personal, and with a
    claude configuration of the run's own."""
    instance = run.suite.mcp is not None
    env = {
        k: v
        for k, v in base.items()
        if not k.startswith("CLAUDE")
        and not (k.startswith("ANTHROPIC_") and k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"))
        and not (k.startswith("IRONFLOCK") and not (instance and k in INSTANCE_VARS))
        and k not in HIDDEN
    }
    env.update(
        CLAUDE_CONFIG_DIR=str(run.state / "claude"),
        CLAUDE_CODE_DISABLE_CLAUDE_MDS="1",
        CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
        DISABLE_AUTOUPDATER="1",
        NPM_CONFIG_USERCONFIG=str(run.state / "npmrc"),
        GH_CONFIG_DIR=str(run.state / "gh"),
        GIT_CONFIG_GLOBAL=str(run.state / "gitconfig"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    if run.suite.name == "widgets" and NODE:
        env["PATH"] = str(Path(NODE).parent) + os.pathsep + env.get("PATH", "")
    if run.suite.name == "cli":
        env["PATH"] = str(EVALS / "cli/fixtures/bin") + os.pathsep + env.get("PATH", "")
        env["IRONFLOCK_EVAL_LOG"] = str(run.cwd / "ironflock-calls.log")
        if run.spec["name"] != "login":
            env["IRONFLOCK_EVAL_LOGGED_IN"] = "1"
    return env


def with_skill_access(settings: dict | None) -> dict:
    """The suite's settings plus the Skill tool and reading the skills' files in
    this checkout. With --permission-prompts none, anything not allowed is
    denied, so without these the with_skill agent cannot load the skill or its
    references. Both configurations get them, so the plugin stays the only
    difference. Read only: the agent must not edit the skill it is graded on."""
    settings = json.loads(json.dumps(settings or {}))
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    for rule in ("Skill", f"Read(/{PLUGINS}/**)"):
        if rule not in allow:
            allow.append(rule)
    return settings


def claude_command(claude: str, run: Run, turn: int, session: str, model: str | None) -> list[str]:
    suite = run.suite
    cmd = [claude, "-p", run.turns[turn], "--output-format", "stream-json", "--verbose"]
    cmd += ["--session-id", session] if turn == 0 else ["--resume", session]
    cmd += ["--setting-sources", "user", "--strict-mcp-config", "--permission-mode", suite.mode, "--permission-prompts", "none"]
    if suite.mcp:
        cmd += ["--mcp-config", str(suite.mcp)]
    settings = cli_settings(suite.evals) if suite.name == "cli" else suite.settings
    cmd += ["--settings", json.dumps(with_skill_access(settings), separators=(",", ":"))]
    if suite.system:
        cmd += ["--append-system-prompt", suite.system]
    if run.config == "with_skill":
        for plugin in suite.plugins:
            cmd += ["--plugin-dir", str(PLUGINS / plugin)]
    if model:
        cmd += ["--model", model]
    return cmd


# --- planning and checks ----------------------------------------------------


def plan(suite: Suite, iteration: Path, only: list[str], configs: tuple[str, ...], values: dict) -> list[Run]:
    runs = []
    for spec in suite.evals["evals"]:
        if only and spec["name"] not in only:
            continue
        for config in configs:
            run = Run(suite, spec, config, iteration)
            run.prompt = fill(spec["prompt"], values) if suite.name in INSTANCE_SUITES else spec["prompt"]
            runs.append(run)
    return runs


def find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    local = Path.home() / ".local/bin/claude"
    return str(local) if local.is_file() and os.access(local, os.X_OK) else None


def inside_git(path: Path) -> bool:
    probe = path
    while not probe.exists():
        probe = probe.parent
    done = subprocess.run(["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    return done.returncode == 0 and done.stdout.strip() == "true"


def load_placeholders(iteration: Path) -> dict | None:
    path = iteration / "placeholders.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def preflight(suites: list[Suite], iteration: Path, args, pending: bool) -> list[str]:
    """Everything that would stop the runs, found before the first one starts."""
    problems = []
    if shutil.which("git") and inside_git(iteration):
        problems.append(
            f"{iteration} is inside a git checkout. Put the iteration outside every checkout "
            "(for example ~/ironflock-evals/1.0.0), so that no agent sees the repository or its skills."
        )
    if pending and not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append(
            "ANTHROPIC_API_KEY is not set. The runs use an API key only, never your Claude login: "
            "export ANTHROPIC_API_KEY in this shell, then run the same command again."
        )
    names = {s.name for s in suites}
    if "templates" in names and not shutil.which("uv"):
        problems.append("uv is not installed; the templates grader runs with uv run.")
    if "widgets" in names:
        if not shutil.which("git"):
            problems.append("git is not installed; the widgets need it.")
        if not NODE or not (Path(NODE).parent / "npm").exists():
            problems.append("node and npm are not installed (not on the PATH, not in ~/.nvm); the widgets need them.")
    if pending and names & set(INSTANCE_SUITES):
        missing = [v for v in INSTANCE_VARS if not os.environ.get(v)]
        if missing:
            problems.append(
                f"{' and '.join(missing)} not set: fleet and data run against a local IronFlock test instance only. "
                "Set its API address and a key of that instance."
            )
        elif problem := host_problem(os.environ["IRONFLOCK_EVAL_API_URL"], args.allow_host):
            problems.append(problem)
    if "cli" in names:
        if not args.in_container:
            problems.append("cli runs only in a throwaway container or virtual machine: pass --in-container there, never on a developer's machine.")
        elif platform.system() == "Darwin":
            problems.append("cli refuses to run on macOS: run it in a throwaway Linux container or virtual machine.")
        else:
            real = shutil.which("ironflock")
            if real:
                problems.append(f"a real ironflock command is installed ({real}); the cli evals need a machine without one.")
            ssh = Path.home() / ".ssh"
            keys = [p.name for p in ssh.glob("id_*") if not p.name.endswith(".pub")] if ssh.is_dir() else []
            if keys:
                problems.append(f"{ssh} holds private keys ({', '.join(keys)}); the cli evals need a machine without them.")
    return problems


def check_placeholders(suites: list[Suite], iteration: Path, write: bool) -> tuple[dict, list[str]]:
    """The placeholder values, and what stops the runs. Writes a template when
    the file is missing and write is set."""
    instance = [s for s in suites if s.name in INSTANCE_SUITES]
    if not instance:
        return {}, []
    keys = placeholder_keys([SUITES[n] for n in INSTANCE_SUITES])
    path = iteration / "placeholders.json"
    values = load_placeholders(iteration)
    describe = "\n".join(f"  {k}: {t}" for k, texts in keys.items() for t in texts)
    if values is None:
        if write:
            iteration.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({k: "" for k in keys}, indent=2) + "\n", encoding="utf-8")
            return {}, [f"{path} did not exist; it does now, with empty values. Fill in the names of the local test instance's demo data:\n{describe}"]
        return {}, [f"{path} is missing (a real run writes a template). The keys:\n{describe}"]
    missing = missing_placeholders(values, [k for s in instance for k in s.evals.get("placeholders", {})])
    if missing:
        return values, [f"{path} has no value for {', '.join(dict.fromkeys(missing))}:\n{describe}"]
    return values, []


# --- running ----------------------------------------------------------------


class Control:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.reason = ""
        self.failures = 0
        self.procs: set[subprocess.Popen] = set()
        self.done = 0

    def halt(self, reason: str) -> None:
        with self.lock:
            if not self.stop.is_set():
                self.reason = reason
                self.stop.set()

    def say(self, text: str) -> None:
        with self.lock:
            print(text, flush=True)


def reset(run: Run) -> None:
    """A fresh run folder and state folder, the agent's folder ready."""
    for path in (run.dir, run.state):
        if path.exists():
            shutil.rmtree(path)
    run.state.mkdir(parents=True)
    (run.state / "gh").mkdir()
    (run.state / "npmrc").write_text("")
    (run.state / "gitconfig").write_text("[user]\n\tname = eval\n\temail = eval@example.invalid\n")
    if run.suite.name == "templates":
        fixture = run.spec.get("fixture", run.suite.evals.get("fixture"))
        if fixture:
            shutil.copytree(REPO / fixture, run.cwd)
        else:
            run.cwd.mkdir(parents=True)
    elif run.suite.name != "widgets":
        run.cwd.mkdir(parents=True)


def set_up_widgets(runs: list[Run], iteration: Path) -> None:
    """Clone the widget fixtures (grade.py setup) and give each run its own."""
    if not runs:
        return
    staging = iteration / ".state" / "widgets-setup"
    if staging.exists():
        shutil.rmtree(staging)
    print("Cloning the widget fixtures (evals/widgets/grade.py setup) ...", flush=True)
    subprocess.run([PY, str(EVALS / "widgets/grade.py"), "setup", str(staging)], check=True, stdout=subprocess.DEVNULL)
    for run in runs:
        run.dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging / run.spec["name"] / run.config / "ironflock-widgets"), str(run.dir / "ironflock-widgets"))
    shutil.rmtree(staging)


def turn(cmd: list[str], run: Run, env: dict, control: Control, timeout: float, check_init: bool) -> tuple[dict | None, str]:
    """One claude process; its stream is appended to the run's partial
    transcript. Returns the result event, or None and why."""
    part = run.state / (FINISHED + ".part")
    timed_out = threading.Event()
    result, problem = None, ""
    with open(part, "a", encoding="utf-8") as out, open(run.state / "stderr.txt", "a", encoding="utf-8") as err:
        proc = subprocess.Popen(cmd, cwd=run.cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8")
        with control.lock:
            control.procs.add(proc)
        timer = threading.Timer(timeout, lambda: (timed_out.set(), proc.kill()))
        timer.start()
        try:
            for line in proc.stdout:
                out.write(line)
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if check_init and event.get("type") == "system" and event.get("subtype") == "init":
                    problems = init_problems(event, run.suite, run.config)
                    if problems:
                        problem = "; ".join(problems)
                        proc.kill()
                        control.halt(f"{run.label}: {problem}")
                        break
                if refused := key_refused(event):
                    problem = refused
                    proc.kill()
                    control.halt(refused)
                    break
                if event.get("type") == "result":
                    result = event
            proc.wait()
        finally:
            timer.cancel()
            with control.lock:
                control.procs.discard(proc)
    if problem:
        return None, problem
    if timed_out.is_set():
        return None, f"stopped after {timeout / 60:.0f} minutes (--timeout)"
    if result is None:
        return None, f"claude exited with {proc.returncode} without a result; see {run.state / 'stderr.txt'}"
    if result.get("is_error"):
        return None, f"claude reported an error: {str(result.get('result') or result.get('subtype'))[:300]}"
    return result, ""


def execute(run: Run, claude: str, args, control: Control, total: int) -> bool:
    if control.stop.is_set():
        return False
    env = run_env(run, dict(os.environ))
    session = str(uuid.uuid4())
    started = time.time()
    results = []
    for i in range(len(run.turns)):
        cmd = claude_command(claude, run, i, session, args.model)
        result, problem = turn(cmd, run, env, control, args.timeout * 60, check_init=i == 0)
        if result is None:
            with control.lock:
                control.failures += 1
                failures = control.failures
            control.say(f"FAILED {run.label}: {problem}")
            if failures >= MAX_FAILURES:
                control.halt(f"{failures} runs failed")
            return False
        results.append(result)
    replies = [str(r.get("result") or "") for r in results]
    (run.dir / run.suite.reply).write_text(replies[-1], encoding="utf-8")
    if len(replies) > 1:
        (run.dir / "QUESTIONS.md").write_text(replies[0], encoding="utf-8")
    meta = {
        "suite": run.suite.name,
        "eval": run.spec["name"],
        "config": run.config,
        "session": session,
        "date": date.today().isoformat(),
        "prompts": run.turns,
        "cost_usd": sum(float(r.get("total_cost_usd") or 0) for r in results),
        "duration_ms": sum(int(r.get("duration_ms") or 0) for r in results),
        "turns": sum(int(r.get("num_turns") or 0) for r in results),
        "permission_denials": [d for r in results for d in r.get("permission_denials") or []],
    }
    if run.config == "without_skill":
        meta["skill_lookups"] = skill_lookups(run.state / (FINISHED + ".part"))
        if meta["skill_lookups"]:
            control.say(f"WARNING {run.label} reached for the skill ({len(meta['skill_lookups'])} tool calls), "
                        f"its score is not a baseline: {meta['skill_lookups'][0][:160]}")
    (run.dir / "RUN.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    shutil.move(str(run.state / (FINISHED + ".part")), str(run.dir / FINISHED))
    with control.lock:
        control.done += 1
        done = control.done
    control.say(f"[{done}/{total}] {run.label}: done in {(time.time() - started) / 60:.1f} min, ${meta['cost_usd']:.2f}")
    return True


# --- grading and summary ----------------------------------------------------


def grade(suite: Suite, iteration: Path, values: dict) -> None:
    """Run the suite's grader; its output goes to <suite>/GRADES.txt."""
    root = iteration / suite.name
    if not root.is_dir():
        return
    for stale in unfinished_dirs(iteration, suite):
        print(f"removing the unfinished run {stale.relative_to(iteration)} before grading", flush=True)
        shutil.rmtree(stale)
    if suite.name in INSTANCE_SUITES:
        (root / "placeholders.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    print(f"\n== grading {suite.name}: {shlex.join([*suite.grader, str(root)])}", flush=True)
    done = subprocess.run([*suite.grader, str(root)], cwd=REPO, capture_output=True, text=True)
    output = done.stdout + (f"\n{done.stderr}" if done.returncode else "")
    print(output, flush=True)
    (root / "GRADES.txt").write_text(output, encoding="utf-8")


def all_grades(iteration: Path) -> dict[str, dict[str, tuple[int, int]]]:
    """The totals of every suite graded in this iteration so far, from its GRADES.txt."""
    return {
        name: parse_totals((iteration / name / "GRADES.txt").read_text(encoding="utf-8"))
        for name in SUITES
        if (iteration / name / "GRADES.txt").is_file()
    }


def score(totals: dict, config: str, tainted: int = 0) -> str:
    if config not in totals:
        return "-"
    p, t = totals[config]
    return f"{p}/{t}" + (f" ({tainted} read the skill)" if tainted and config == "without_skill" else "")


def minutes(ms: float) -> str:
    m = round(ms / 60000)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


def summary(iteration: Path, graded: dict[str, dict], model_flag: str | None) -> str:
    rows, models, versions, tainted = [], set(), set(), []
    cost = duration = runs = 0
    for name, totals in graded.items():
        suite = SUITES[name]
        suite_tainted = tainted_runs(iteration, name)
        tainted += [(f"{name}/{e}", lookups) for e, lookups in suite_tainted.items()]
        s_cost = s_ms = s_runs = 0
        for transcript in sorted((iteration / name).glob(f"*/*/{FINISHED}")):
            stats = transcript_stats(transcript)
            s_cost += stats["cost"]
            s_ms += stats["duration_ms"]
            s_runs += 1
            models |= stats["models"]
            versions |= stats["versions"]
        cost, duration, runs = cost + s_cost, duration + s_ms, runs + s_runs
        rows.append((name, suite.skill, score(totals, "with_skill"), score(totals, "without_skill", len(suite_tainted)), s_runs, s_cost, s_ms))
    today = date.today().isoformat()
    model = ", ".join(sorted(models)) or (model_flag or "claude's default")
    version = ", ".join(sorted(versions)) or "unknown"
    lines = [
        f"# Evals in {iteration.name}",
        "",
        f"{today}, model {model}, Claude Code {version}, {runs} runs, ${cost:.2f}, {minutes(duration)} of run time "
        "(summed over the runs' result events).",
        "",
        "| Suite | Skill | With the skill | Without | Runs | Cost | Run time |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {n} | {sk} | {w} | {wo} | {r} | ${c:.2f} | {minutes(ms)} |" for n, sk, w, wo, r, c, ms in rows]
    lines += [
        "",
        "Each run: `claude -p` in its own folder (evals/run.py), with a configuration of its own: "
        "no CLAUDE.md, memory, hooks, settings, plugins or MCP servers of the person who ran it. "
        "With the skill it loaded the plugin from the checkout with --plugin-dir; without, no plugin. "
        "The grader output of each suite is in <suite>/GRADES.txt.",
        "",
    ]
    if tainted:
        lines += [
            "## Runs without the skill that read it",
            "",
            "These agents fetched the skill themselves (from GitHub, a clone or the installed plugins), so their "
            "scores are no baseline. They are still counted in the Without column; the tool calls are in each "
            "run's RUN.json (skill_lookups).",
            "",
        ]
        lines += [f"- {label}: {len(lookups)} tool calls, first: `{lookups[0][:160]}`" for label, lookups in tainted]
        lines.append("")
    lines += [
        "To record this run (optional), the sections for evals/results/<version>.md:",
        "",
    ]
    for n, sk, w, wo, *_ in rows:
        lines += [f"## {sk}", "", f"Result: {w} with the skill, {wo} without ({today}, {model}, Claude Code {version}, evals/run.py).", ""]
    return "\n".join(lines)


def print_table(iteration: Path, graded: dict[str, dict]) -> None:
    print(f"\n{'Suite':10} {'With the skill':15} {'Without':10}")
    for name, totals in graded.items():
        without = score(totals, "without_skill", len(tainted_runs(iteration, name)))
        print(f"{name:10} {score(totals, 'with_skill'):15} {without:10}")
    print(f"\nSummary: {iteration / 'SUMMARY.md'}")


# --- main -------------------------------------------------------------------


def dry_run(runs: list[Run], suites: list[Suite], iteration: Path, claude: str, args) -> None:
    print("Each run gets its own claude configuration and no personal settings, CLAUDE.md, memory, plugins,")
    print("MCP servers or npm/GitHub/git credentials; the environment it adds (shown for the first run):")
    if runs:
        env = run_env(runs[0], {})
        print("  " + " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items() if k != "PATH"))
    print("ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL) are passed on from this shell.\n")
    for run in runs:
        session = "<new uuid>"
        print(f"# {run.label}")
        print(f"cd {shlex.quote(str(run.cwd))}")
        if run.suite.name == "cli":
            env = run_env(run, {})
            extra = " ".join(f"{k}={shlex.quote(env[k])}" for k in ("IRONFLOCK_EVAL_LOG", "IRONFLOCK_EVAL_LOGGED_IN") if k in env)
            print(f'export PATH={shlex.quote(str(EVALS / "cli/fixtures/bin"))}:"$PATH" {extra}')
        for i in range(len(run.turns)):
            print(shlex.join(claude_command(claude, run, i, session, args.model)) + f" >> {FINISHED}")
        print()
    for suite in suites:
        print(f"# grade: {shlex.join([*suite.grader, str(iteration / suite.name)])}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="evals/run.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", choices=["all", *SUITES])
    parser.add_argument("iteration", type=Path)
    parser.add_argument("--only", action="append", default=[], metavar="EVAL")
    parser.add_argument("--config", choices=["with", "without"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=60, help="minutes per turn")
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--in-container", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    iteration = args.iteration.expanduser().resolve()
    suites = [SUITES[n] for n in (ALL if args.suite == "all" else (args.suite,))]
    configs = (f"{args.config}_skill",) if args.config else CONFIGS
    names = {spec["name"] for s in suites for spec in s.evals["evals"]}
    unknown = [n for n in args.only if n not in names]
    if unknown:
        print(f"no eval named {', '.join(unknown)} in {', '.join(s.name for s in suites)}", file=sys.stderr)
        return 2
    claude = find_claude()
    if not claude:
        print("Claude Code is not installed: no claude on the PATH and none in ~/.local/bin.", file=sys.stderr)
        return 2

    values, placeholder_problems = check_placeholders(suites, iteration, write=not args.dry_run)
    runs = [r for s in suites for r in plan(s, iteration, args.only, configs, values)]
    pending = to_run(runs, args.force)
    problems = preflight(suites, iteration, args, bool(pending)) + (placeholder_problems if pending else [])
    if args.dry_run:
        dry_run(pending, suites, iteration, claude, args)
        for p in problems:
            print(f"\nA real run would stop here: {p}")
        return 0
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2

    skipped = len(runs) - len(pending)
    print(f"{len(pending)} runs to do" + (f", {skipped} finished already (--force runs them again)" if skipped else "") + f", {args.jobs} at a time.", flush=True)
    control = Control()
    for run in pending:
        reset(run)
    set_up_widgets([r for r in pending if r.suite.name == "widgets"], iteration)
    pool = ThreadPoolExecutor(max_workers=max(1, args.jobs))
    futures = [pool.submit(execute, r, claude, args, control, len(pending)) for r in pending]
    try:
        ok = [f.result() for f in futures]
    except KeyboardInterrupt:
        control.halt("interrupted")
        with control.lock:
            for proc in control.procs:
                proc.kill()
        pool.shutdown(wait=False, cancel_futures=True)
        print("\nInterrupted. Finished runs are kept; the same command goes on with the rest.", file=sys.stderr)
        return 130
    pool.shutdown()
    failed = ok.count(False)
    if control.stop.is_set():
        print(f"\nStopped: {control.reason}. Finished runs are kept; fix the cause and run the same command again.", file=sys.stderr)

    for suite in suites:
        grade(suite, iteration, values)
    graded = all_grades(iteration)
    (iteration / "SUMMARY.md").write_text(summary(iteration, graded, args.model), encoding="utf-8")
    print_table(iteration, graded)
    if failed:
        print(f"{failed} runs did not finish; the same command runs them again.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
