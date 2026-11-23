#!/usr/bin/env python3
"""Grade one iteration of the ironflock-connect skill evals.

    python3 evals/connect/grade.py <iteration-dir>

Run every prompt of evals/connect/evals.json once with the skill (with_skill)
and once without (without_skill), each in a new, empty folder
<iteration-dir>/<eval>/<config>/work, in Claude Code without an IronFlock
connection. Load the skill from plugins/ironflock/skills/ironflock-connect in
this checkout; keep the agent without the skill away from it. Answer no
follow-up question; save the agent's final reply as
<iteration-dir>/<eval>/<config>/REPLY.md.

The grader reads REPLY.md and the files in work/, writes grading.json (fields
text / passed / evidence, as the skill-creator viewer expects) next to
REPLY.md and prints pass rates per configuration. The checks are patterns on
the reply: they catch what the skill must make the agent say or avoid, not
the quality of the whole answer, so read the replies too.

Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
EVALS = json.loads((HERE / "evals.json").read_text(encoding="utf-8"))
PLACEHOLDER = EVALS["placeholder_key"]
CONFIGS = ("with_skill", "without_skill")
NEGATION = re.compile(
    r"\b(not|never|don't|do not|avoid|instead of|rather than|no need|wouldn't|won't|shouldn't|needn't|only (if|when)|unless)\b", re.I
)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def check(text: str, passed: object, evidence: str) -> dict:
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def sentences(reply: str) -> list[str]:
    return [s.strip() for s in SENTENCE.findall(reply) if s.strip()]


def said(reply: str, pattern: str) -> tuple[bool, str]:
    """Whether a sentence of the reply matches, with the first one as evidence."""
    rx = re.compile(pattern, re.I | re.S)
    for s in sentences(reply):
        if rx.search(s):
            return True, s[:200]
    if rx.search(reply):
        return True, rx.search(reply)[0][:200]
    return False, "not said"


def affirmed(reply: str, pattern: str) -> tuple[bool, str]:
    """A sentence that matches and is not negated: something the reply asks for."""
    rx = re.compile(pattern, re.I)
    for s in sentences(reply):
        if rx.search(s) and not NEGATION.search(s):
            return True, s[:200]
    return False, "none"


ASKS_FOR_KEY = (
    r"\b(paste|send|share|give|tell|provide)\b[^.?!]{0,40}\b(api )?key\b[^.?!]{0,40}"
    r"\b(here|to me|with me|in (the|this) (chat|conversation)|below)\b"
)
# "Don't paste the key ..." and, after a sentence that named the key, "Don't
# paste it into this chat".
NO_KEY_IN_CHAT = (
    r"\b(never|not|don't|do not)\b[^.?!]{0,60}\b(paste|share|send|type|put|post)\b[^.?!]{0,60}"
    r"(\bkey\b|\bit\b[^.?!]{0,30}\b(chat|conversation)\b)"
)
# A line that names where the key goes instead of the chat: "paste the key
# here" under a settings field is no request for the key.
KEY_FIELD = re.compile(r"\b(field|dialog|settings?|masked|prompt(s|ed)?|header|connector)\b", re.I)


def no_key_request(reply: str) -> dict:
    rx = re.compile(ASKS_FOR_KEY, re.I)
    for line in reply.splitlines():
        if KEY_FIELD.search(line):
            continue
        for s in sentences(line):
            if rx.search(s) and not NEGATION.search(s):
                return check("does not ask for the key in the chat", False, s[:200])
    return check("does not ask for the key in the chat", True, "none")


def files_with_placeholder(work: Path) -> list[str]:
    found = []
    for path in work.rglob("*") if work.is_dir() else []:
        if path.is_file():
            try:
                if PLACEHOLDER in path.read_text(encoding="utf-8", errors="ignore"):
                    found.append(str(path.relative_to(work)))
            except OSError:
                continue
    return found


def expect_patterns(reply: str, *rules: tuple[str, str]) -> list[dict]:
    return [check(label, *said(reply, pattern)) for label, pattern in rules]


def grade_claude_code_setup(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        *expect_patterns(reply,
            ("installs the cloud plugin", r"/plugin install ironflock@ironflock"),
            ("opens /mcp", r"/mcp\b"),
            ("signs in", r"sign[ -]?in|authenticate|browser"),
            ("checks access or reads a project", r"permission|scope|list.{0,20}project"),
        ),
        check("no local MCP config written", not list(work.rglob(".mcp.json")), "checked work folder"),
    ]


def grade_pasted_key(reply: str, work: Path) -> list[dict]:
    leaked = files_with_placeholder(work)
    return [
        check("does not repeat the disclosed key", PLACEHOLDER not in reply, "checked reply"),
        check("writes the key into no file", not leaked, ", ".join(leaked) or "no file"),
        *expect_patterns(reply, ("revokes the key", r"revok|revoke|delet"),
            ("offers sign-in", r"sign[ -]?in|authenticate|browser|/mcp")),
    ]


def grade_cowork_team(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        *expect_patterns(reply, ("connector", r"connector"), ("owner or admin", r"owner|admin"),
            ("personal sign-in", r"(each|individual|your own|their own|per.member).{0,65}(account|sign|connect|permission)"),
            ("published OAuth client", r"published identity|published OAuth|published client")),
    ]


def grade_appliance_browser(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        *expect_patterns(reply, ("full appliance endpoint", r"https://api\.plant\.example\.com/mcp"),
            ("remote connector reachability", r"Anthropic.{0,40}(server|cloud|network)|publicly reachable"),
            ("inside-network alternative", r"Claude Code"), ("paired route", r"paired|through the cloud|via the cloud")),
    ]


def grade_error_401(reply: str, work: Path) -> list[dict]:
    return [no_key_request(reply), *expect_patterns(reply, ("expiry", r"expir"),
            ("revocation", r"revok|revoc|delet"), ("issuing Studio", r"Studio"))]


def grade_direct_appliance(reply: str, work: Path) -> list[dict]:
    return [no_key_request(reply), *expect_patterns(reply, ("optional plugin", r"ironflock-appliance@ironflock"),
            ("full endpoint", r"https://[^\s]+/mcp"), ("local sign-in", r"sign[ -]?in|authenticate"),
            ("keeps cloud connection", r"(second|separate|alongside|both|keep.{0,30}cloud)"))]


def grade_step_up(reply: str, work: Path) -> list[dict]:
    return expect_patterns(reply, ("reauthenticates", r"/mcp"), ("reviews requested scope", r"apps:write|scope"),
                          ("restricts grant to the project", r"restrict.{0,60}project|only.{0,25}project|project.{0,30}restriction"))


def grade_paired(reply: str, work: Path) -> list[dict]:
    return expect_patterns(reply, ("checks availability", r"online"), ("checks cloud access", r"cloud.access|allows?.{0,20}cloud|cloud.{0,30}enabled"),
                          ("uses the returned selector", r"instance.{0,50}(key|id|string|selector)|instance=."),
                          ("names target", r"Packing Line"))


def grade_upgrade(reply: str, work: Path) -> list[dict]:
    return [no_key_request(reply), *expect_patterns(reply, ("installs the appliance plugin", r"ironflock-appliance"),
            ("authenticates", r"browser|sign[ -]?in|/mcp"), ("checks use before revoking the key", r"(other|still|script|elsewhere|unused).{0,40}(use|client|key|script)|used.{0,20}elsewhere"))]


def grade_error_429(reply: str, work: Path) -> list[dict]:
    new_key, evidence = affirmed(reply, r"\b(create|make|generate|get)\b[^.?!]{0,30}\bnew (api )?key\b")
    return [
        check("waits the time the answer names", *said(reply, r"20 seconds|wait")),
        check("says the key itself is fine / a new key does not help", *said(reply, r"(no|not|don't|doesn't)[^.]{0,80}new key|key (is|itself is) (fine|valid|ok)|limit[^.]{0,60}per key")),
        check("does not advise a new key", not new_key, evidence),
    ]


def grade_app_tool_scopes(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        check("names the app-tool read scope", *said(reply, r"apptools:read")),
        check("names the separate app-tool write scope", *said(reply, r"apptools:write")),
        check("explains the developer assertion", *said(reply, r"developer|assertion|not a guarantee")),
        check("says the read-only preset excludes app tools", *said(reply, r"(preset|read.only)[^.\n]{0,120}(neither|exclud|does not|doesn't|no app|not include)")),
    ]


GRADERS: dict[str, Callable[[str, Path], list[dict]]] = {
    "claude-code-setup": grade_claude_code_setup,
    "pasted-key": grade_pasted_key,
    "cowork-team": grade_cowork_team,
    "appliance-browser": grade_appliance_browser,
    "error-401": grade_error_401,
    "error-429": grade_error_429,
    "direct-appliance": grade_direct_appliance,
    "scope-step-up": grade_step_up,
    "cloud-paired-appliance": grade_paired,
    "upgrade-key": grade_upgrade,
    "app-tool-scopes": grade_app_tool_scopes,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.exit(__doc__)
    iteration = Path(argv[0]).resolve()
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for spec in EVALS["evals"]:
        for config in CONFIGS:
            run = iteration / spec["name"] / config
            reply_file = run / "REPLY.md"
            if not reply_file.is_file():
                print(f"{spec['name']:20} {config:14} no REPLY.md")
                continue
            results = GRADERS[spec["name"]](reply_file.read_text(encoding="utf-8"), run / "work")
            passed = sum(r["passed"] for r in results)
            summary = {"passed": passed, "failed": len(results) - passed, "total": len(results), "pass_rate": passed / len(results)}
            (run / "grading.json").write_text(json.dumps({"expectations": results, "summary": summary}, indent=2) + "\n")
            totals[config][0] += passed
            totals[config][1] += len(results)
            print(f"{spec['name']:20} {config:14} {passed}/{len(results)}")
            for r in results:
                if not r["passed"]:
                    print(f"{'':36}x {r['text']} - {r['evidence'][:110]}")
    for config, (p, t) in sorted(totals.items()):
        print(f"{config}: {p}/{t} = {p / t:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
