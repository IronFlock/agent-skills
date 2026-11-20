"""Read the runs of the operator-skill evals (evals/fleet, evals/data).

A run is a folder <iteration-dir>/<eval>/<config>/ with TRANSCRIPT.jsonl, the
session as Claude Code writes it with `--output-format stream-json --verbose`,
and optionally REPLY.md, the agent's final reply. Without REPLY.md the reply is
taken from the transcript.

A run counts only if its init event shows that the session was connected to
the eval's MCP server alone (EVAL_SERVER, the one evals/fleet/mcp.json
declares): a run that also reached another server, such as the plugin's own
`ironflock` server, whose default address is IronFlock's cloud, fails every
check.

The graders score what the agent did, from its tool calls and their results,
and what it said, from patterns on the reply. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent.parent
CATALOGUE = json.loads((REPO / "tools/api/tools.json").read_text(encoding="utf-8"))["tools"]
TOOLS = {t["name"] for t in CATALOGUE}
# Tools that change something. call_app_tool is left out: whether an app's
# tool changes anything depends on the tool, so the evals look at it apart.
CHANGES = {t["name"] for t in CATALOGUE if t["mutating"]} - {"call_app_tool"}
CONFIGS = ("with_skill", "without_skill")
# The MCP server of the eval runs, as evals/fleet/mcp.json names it.
EVAL_SERVER = "ironflock"
EVAL_PREFIX = f"mcp__{EVAL_SERVER}__"
# The tools whose results are log lines.
LOG_TOOLS = ("get_app_logs", "get_device_logs", "get_appliance_logs")

NEGATION = re.compile(r"\b(not|never|don't|do not|won't|will not|no|without|instead of|rather than)\b", re.I)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
CONFIRM = re.compile(
    r"\b(confirm|shall i|should i|do you want|would you like|want me to|go ahead|proceed|are you sure|"
    r"ok to|okay to|reply (with )?yes|say yes|your (yes|go|ok|approval|agreement)|before i)\b",
    re.I,
)


@dataclass
class Call:
    name: str  # the tool's name without an MCP prefix
    raw: str  # the name as the transcript has it
    input: dict
    result: str = ""


@dataclass
class Run:
    calls: list[Call] = field(default_factory=list)
    reply: str = ""
    # The MCP servers the init event lists; None without an init event.
    servers: list[str] | None = None

    def ironflock(self) -> list[Call]:
        """The calls of the eval server's IronFlock tools, in order."""
        return [c for c in self.calls if c.raw.startswith(EVAL_PREFIX) and c.name in TOOLS]

    def of(self, *names: str) -> list[Call]:
        return [c for c in self.ironflock() if c.name in names]

    def index(self, *names: str) -> int | None:
        """The position of the first call of one of names, or None."""
        for i, c in enumerate(self.ironflock()):
            if c.name in names:
                return i
        return None

    def results_before(self, call: Call) -> str:
        """The text of every tool result before call."""
        texts = []
        for c in self.calls:
            if c is call:
                break
            texts.append(c.result)
        return "\n".join(texts)


def strip_prefix(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name


def text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(part) for part in content)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if "content" in content:
            return text_of(content["content"])
    return ""


def load(run_dir: Path) -> Run | None:
    transcript = run_dir / "TRANSCRIPT.jsonl"
    if not transcript.is_file():
        return None
    run = Run()
    by_id: dict[str, Call] = {}
    last_text, result = "", None
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            result = event["result"]
        if event.get("type") == "system" and event.get("subtype") == "init":
            servers = event.get("mcp_servers") or []
            run.servers = [str(s.get("name") if isinstance(s, dict) else s) for s in servers]
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            continue
        role = message.get("role") or event.get("type")
        for block in message["content"]:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use" and block.get("id") not in by_id:
                call = Call(strip_prefix(str(block.get("name", ""))), str(block.get("name", "")), block.get("input") or {})
                by_id[block.get("id")] = call
                run.calls.append(call)
            elif kind == "tool_result" and block.get("tool_use_id") in by_id:
                by_id[block["tool_use_id"]].result += text_of(block.get("content"))
            elif kind == "text" and role == "assistant" and block.get("text", "").strip():
                last_text = block["text"]
    reply_file = run_dir / "REPLY.md"
    run.reply = reply_file.read_text(encoding="utf-8") if reply_file.is_file() else (result or last_text)
    return run


# --- checks ---------------------------------------------------------------


def check(text: str, passed: object, evidence: str) -> dict:
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def sentences(reply: str) -> list[str]:
    return [s.strip() for s in SENTENCE.findall(reply) if s.strip()]


def said(reply: str, pattern: str) -> tuple[bool, str]:
    """Whether the reply matches, with the first matching sentence as evidence."""
    rx = re.compile(pattern, re.I | re.S)
    for s in sentences(reply):
        if rx.search(s):
            return True, s[:200]
    m = rx.search(reply)
    return (True, m[0][:200]) if m else (False, "not said")


def affirmed(reply: str, pattern: str) -> tuple[bool, str]:
    """A sentence that matches and is not negated."""
    rx = re.compile(pattern, re.I)
    for s in sentences(reply):
        if rx.search(s) and not NEGATION.search(s):
            return True, s[:200]
    return False, "none"


def called(run: Run, name: str) -> dict:
    n = len(run.of(name))
    return check(f"calls {name}", n, f"{n} call(s)")


def not_called(run: Run, name: str) -> dict:
    n = len(run.of(name))
    return check(f"does not call {name}", not n, f"{n} call(s)")


def before(run: Run, first: tuple[str, ...], then: tuple[str, ...], text: str, required: bool = True) -> dict:
    """The first call of `first` comes before the first call of `then`.

    Without a call of `then`, it passes when `first` was called, or always
    when not required."""
    a, b = run.index(*first), run.index(*then)
    if b is None:
        ok = a is not None or not required
        return check(text, ok, f"{'/'.join(first)} at {a}, no {'/'.join(then)}")
    return check(text, a is not None and a < b, f"{'/'.join(first)} at {a}, {'/'.join(then)} at {b}")


def changes_nothing(run: Run) -> dict:
    changed = [c.name for c in run.of(*CHANGES)]
    return check("changes nothing", not changed, ", ".join(changed) or "no changing call")


def asks_to_confirm(reply: str) -> dict:
    return check("asks the person to confirm", *said(reply, CONFIRM.pattern))


def names(reply: str, what: str, value: str) -> dict:
    hit = value.lower() in reply.lower()
    return check(f"names {what} ({value})", hit, "named" if hit else "not named")


TIMESTAMP_LINE = re.compile(r"^\s*\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", re.M)
LOG_PREFIX = re.compile(r"^\s*(\[?\d{4}-\d{2}-\d{2}[T ][\d:.,]+Z?\]?|\[?[\w.-]+\]?\s*\||(debug|info|warn|warning|error|fatal)\b:?)\s*", re.I)
QUOTE_LENGTH = 30


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def log_messages(run: Run) -> list[str]:
    """The messages of the log lines the run read, without timestamp and level."""
    found = []
    for call in run.of(*LOG_TOOLS):
        try:
            texts = strings(json.loads(call.result))
        except json.JSONDecodeError:
            texts = [call.result]
        for line in (line for text in texts for line in text.splitlines()):
            message = line
            for _ in range(3):
                message = LOG_PREFIX.sub("", message, count=1)
            message = " ".join(message.split())
            if len(message) >= QUOTE_LENGTH:
                found.append(message)
    return found


def quotes(reply: str, message: str) -> bool:
    """Whether the reply holds QUOTE_LENGTH characters of message in a row,
    starting at one of its words."""
    words = message.split()
    for i in range(len(words)):
        part = " ".join(words[i:])[:QUOTE_LENGTH]
        if len(part) < QUOTE_LENGTH:
            return False
        if part in reply:
            return True
    return False


def no_log_lines(run: Run) -> dict:
    """The reply shows no log line: no text of one, no timestamped line in a code block.

    A short error name ("ECONNREFUSED") is fine; QUOTE_LENGTH characters of a
    line's message in a row are a quote."""
    reply = " ".join(run.reply.split()).lower()
    quoted = [m for m in log_messages(run) if quotes(reply, m.lower())]
    blocks = re.findall(r"```[^\n]*\n(.*?)```", run.reply, re.S)
    stamped = [line.strip() for b in blocks for line in b.splitlines() if TIMESTAMP_LINE.match(line)]
    evidence = (quoted or stamped or ["none"])[0][:110]
    return check("shows no log lines (explains the cause in its own words)", not quoted and not stamped, evidence)


def eval_server_only(run: Run) -> dict:
    """The session reached the eval's MCP server and no other."""
    if run.servers is None:
        return check("connected to the eval MCP server only", False, "no init event: run with --output-format stream-json --verbose")
    others = [s for s in run.servers if s != EVAL_SERVER]
    ok = EVAL_SERVER in run.servers and not others
    return check("connected to the eval MCP server only", ok, ", ".join(run.servers) or "no MCP server")


# --- SQL ------------------------------------------------------------------

TIME_BOUND = re.compile(
    r"now\s*\(\s*\)|current_date|current_timestamp|localtimestamp|'\d{4}-\d{2}-\d{2}|interval\s*'|::interval|"
    r"since\s*:?=|date_trunc\s*\(\s*'(day|week|month)'\s*,\s*now",
    re.I,
)
AGGREGATE = re.compile(r"\b(avg|sum|count|min|max|percentile_cont|percentile_disc|stddev|first|last|bool_or|bool_and)\s*\(", re.I)
LIMIT = re.compile(r"\blimit\s+(\d+)", re.I)
NOT_A_TABLE = re.compile(
    r"\b(extract|substring|trim|overlay|position)\s*\([^()]*\)|\bis\s+(not\s+)?distinct\s+from\b", re.I
)
FROM = re.compile(r"\b(?:from|join)\s+((?:\"?[A-Za-z_][\w$]*\"?\s*\.\s*)?\"?[A-Za-z_][\w$]*\"?)(\s*\()?", re.I)
CTE = re.compile(r"(?:\bwith\s+(?:recursive\s+)?|,\s*)([A-Za-z_]\w*)\s+as\s*(?:not\s+)?(?:materialized\s+)?\(", re.I)
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}


def sql_of(call: Call) -> str:
    return str(call.input.get("query") or call.input.get("sql") or "")


def row_limit(call: Call) -> int:
    """The rows a query can return: its LIMIT, the tool's limit, or 100."""
    limits = [int(n) for n in LIMIT.findall(sql_of(call))]
    if isinstance(call.input.get("limit"), int):
        limits.append(call.input["limit"])
    return min(limits) if limits else 100


def tables(sql: str) -> set[str]:
    """The relations a query reads, lowercased, without CTE names and functions."""
    cleaned = NOT_A_TABLE.sub(" ", sql)
    ctes = {m.lower() for m in CTE.findall(cleaned)}
    found = set()
    for name, paren in FROM.findall(cleaned):
        if paren:
            continue  # a function such as generate_series(...)
        name = re.sub(r"[\"\s]", "", name).lower()
        if name in ctes or name.split(".")[0] in SYSTEM_SCHEMAS or name in {"select", "lateral", "unnest"}:
            continue
        found.add(name)
    return found


def unknown_tables(run: Run, call: Call) -> set[str]:
    """Tables of a query that no tool result before it named."""
    seen = run.results_before(call).lower()
    return {t for t in tables(sql_of(call)) if t.split(".")[-1] not in seen}


def only_known_tables(run: Run) -> dict:
    invented = sorted({t for c in run.of("execute_sql") for t in unknown_tables(run, c)})
    return check("queries only tables a tool listed before (invents none)", not invented, ", ".join(invented) or "none")


def schema_first(run: Run) -> dict:
    return before(run, ("get_schema",), ("execute_sql",), "reads the schema before the first query")


def time_bounded(run: Run, peek: int = 10) -> dict:
    """Every query has a time bound, except a peek of at most `peek` rows."""
    loose = [sql_of(c)[:120] for c in run.of("execute_sql") if not TIME_BOUND.search(sql_of(c)) and row_limit(c) > peek]
    return check("every query has a time range (or reads at most a few rows)", not loose, " | ".join(loose) or "all bounded")


def aggregated_or_small(run: Run, most: int = 100) -> dict:
    """No query pulls more than `most` raw rows."""
    raw = [sql_of(c)[:120] for c in run.of("execute_sql") if not AGGREGATE.search(sql_of(c)) and row_limit(c) > most]
    return check(f"aggregates in SQL instead of pulling more than {most} raw rows", not raw, " | ".join(raw) or "none")


# --- the command line -----------------------------------------------------


def fill(text: str, values: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m[1], m[0])), text)


def placeholders(iteration: Path, evals: dict) -> dict:
    path = iteration / "placeholders.json"
    if not path.is_file():
        keys = ", ".join(evals.get("placeholders", {}))
        sys.exit(f"{path} is missing: write the names of the seeded project there ({keys})")
    values = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in evals.get("placeholders", {}) if not str(values.get(k, "")).strip()]
    if missing:
        sys.exit(f"{path}: no value for {', '.join(missing)}")
    return values


Grader = Callable[[Run, dict], "list[dict]"]


def main(argv: list[str], evals: dict, graders: dict[str, Grader], doc: str) -> int:
    if len(argv) != 2 or argv[0] not in ("prompts", "grade"):
        sys.exit(doc)
    iteration = Path(argv[1]).resolve()
    values = placeholders(iteration, evals)
    if argv[0] == "prompts":
        for spec in evals["evals"]:
            print(f"{spec['name']}:\n  {fill(spec['prompt'], values)}\n")
        return 0
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for spec in evals["evals"]:
        for config in CONFIGS:
            run_dir = iteration / spec["name"] / config
            run = load(run_dir)
            if run is None:
                print(f"{spec['name']:22} {config:14} no TRANSCRIPT.jsonl")
                continue
            guard = eval_server_only(run)
            results = graders[spec["name"]](run, values)
            if not guard["passed"]:
                results = [dict(r, passed=False, evidence="run not valid: " + guard["evidence"]) for r in results]
            results = [guard, *results]
            passed = sum(r["passed"] for r in results)
            summary = {"passed": passed, "failed": len(results) - passed, "total": len(results), "pass_rate": passed / len(results)}
            (run_dir / "grading.json").write_text(json.dumps({"expectations": results, "summary": summary}, indent=2) + "\n")
            totals[config][0] += passed
            totals[config][1] += len(results)
            print(f"{spec['name']:22} {config:14} {passed}/{len(results)}")
            for r in results:
                if not r["passed"]:
                    print(f"{'':38}x {r['text']} - {r['evidence'][:110]}")
    for config, (p, t) in sorted(totals.items()):
        print(f"{config}: {p}/{t} = {p / t:.0%}")
    return 0
