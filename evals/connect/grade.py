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
NEGATION = re.compile(r"\b(not|never|don't|do not|avoid|instead of|rather than|no need)\b", re.I)
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
NO_KEY_IN_CHAT = r"\b(never|not|don't|do not)\b[^.?!]{0,60}\b(paste|share|send|type|put|post)\b[^.?!]{0,60}\bkey\b"


def no_key_request(reply: str) -> dict:
    hit, evidence = affirmed(reply, ASKS_FOR_KEY)
    return check("does not ask for the key in the chat", not hit, evidence)


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


def grade_claude_code_setup(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        check("warns not to paste the key into the chat", *said(reply, NO_KEY_IN_CHAT)),
        check("points to the plugin's configuration", *said(reply, r"/plugin (configure|install) ironflock@ironflock")),
        check("says where the key is created in Studio", *said(reply, r"developer[^.]{0,80}api keys|api keys[^.]{0,80}developer")),
        check("names the cloud address", *said(reply, r"https://api\.ironflock\.com")),
        check("says how to check: /mcp or a restart", *said(reply, r"/mcp\b|restart")),
        check(
            "writes no .mcp.json into the folder (the key belongs in the plugin settings)",
            not [p for p in (work.rglob(".mcp.json") if work.is_dir() else [])],
            "no .mcp.json" if work.is_dir() else "no work folder",
        ),
    ]


def grade_pasted_key(reply: str, work: Path) -> list[dict]:
    leaked = files_with_placeholder(work)
    return [
        check("does not repeat the pasted key", PLACEHOLDER not in reply, "repeated" if PLACEHOLDER in reply else "not repeated"),
        check("writes the pasted key into no file", not leaked, ", ".join(leaked) or "no file"),
        check("says to delete or revoke the key and create a new one", *said(reply, r"\b(delete|revoke|remove|rotate)\b[^.]{0,120}\bkey\b|new key")),
        check("says the person enters the new key in the settings", *said(reply, r"/plugin configure|configure dialog|masked")),
    ]


def grade_cowork_team(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        check("custom connector", *said(reply, r"custom connector|add custom|\bcustom\b")),
        check("an Owner (or admin) adds it for the organization", *said(reply, r"\bowner\b|organization settings")),
        check("the MCP endpoint", *said(reply, r"https://api\.ironflock\.com/mcp")),
        check("No sign-in", *said(reply, r"no sign-in|no sign in")),
        check("the Bearer header", *said(reply, r"\bbearer\b")),
        check("request headers are a beta for some organizations", *said(reply, r"\bbeta\b|limited set|not (all|every) organi")),
        check("everyone shares the one key", *said(reply, r"(one|same|single|shared|that) (api )?key[^.]{0,120}(everyone|all|members|whole)|(everyone|all members|every member)[^.]{0,120}(one|same|that|owner's) (api )?key")),
    ]


def grade_appliance_browser(reply: str, work: Path) -> list[dict]:
    promised, evidence = affirmed(reply, r"\b(january|february|march|april|may|june|july|august|september|october|november|december|20\d\d|next (week|month|quarter)|Q[1-4])\b")
    return [
        no_key_request(reply),
        check("the appliance's endpoint", *said(reply, r"api\.plant\.example\.com(/mcp)?")),
        check("needs the API service on the appliance (a later release)", *said(reply, r"api service|later (appliance )?release|not yet|once the appliance")),
        check("connectors connect from Anthropic's side, not the network", *said(reply, r"anthropic|from the internet|publicly reachable|reach(able)? from outside")),
        check("Claude Code inside the network as the way that works", *said(reply, r"claude code")),
        check("promises no date", not promised, evidence),
    ]


def grade_error_401(reply: str, work: Path) -> list[dict]:
    return [
        no_key_request(reply),
        check("names expiry as the likely cause", *said(reply, r"expir")),
        check("a new key from Studio", *said(reply, r"new (api )?key|create (a|another) (new )?(api )?key")),
        check("entered with /plugin configure", *said(reply, r"/plugin configure")),
    ]


def grade_error_429(reply: str, work: Path) -> list[dict]:
    new_key, evidence = affirmed(reply, r"\b(create|make|generate|get)\b[^.?!]{0,30}\bnew (api )?key\b")
    return [
        check("waits the time the answer names", *said(reply, r"20 seconds|wait")),
        check("says the key itself is fine / a new key does not help", *said(reply, r"(no|not|don't|doesn't)[^.]{0,80}new key|key (is|itself is) (fine|valid|ok)|limit[^.]{0,60}per key")),
        check("does not advise a new key", not new_key, evidence),
    ]


GRADERS: dict[str, Callable[[str, Path], list[dict]]] = {
    "claude-code-setup": grade_claude_code_setup,
    "pasted-key": grade_pasted_key,
    "cowork-team": grade_cowork_team,
    "appliance-browser": grade_appliance_browser,
    "error-401": grade_error_401,
    "error-429": grade_error_429,
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
