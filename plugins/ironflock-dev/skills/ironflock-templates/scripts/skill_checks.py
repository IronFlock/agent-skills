"""App-skill checks for validate.py.

An app skill is an instruction file the app ships for its own AI agents:
.ironflock/skills/<name>/SKILL.md, with optional
.ironflock/skills/<name>/references/<file>.md, listed by the agents that may
load it in ai-template.yml (`skills: [<name>]`). The release build refuses an
app whose skills break any of the rules below, so each one is an ERROR here:

- the folder holds only skill folders, a skill folder only SKILL.md and
  references/<file>.md, every file is UTF-8 text and nothing is a symbolic link;
- SKILL.md starts with YAML frontmatter holding `name` (the folder's name) and
  `description`, followed by the instructions;
- the limits on names, the description, the instructions, the reference files,
  the number of skills and their total size;
- every entry of an agent's `skills` names a skill folder of the app (or an open
  platform skill as platform/<name>), and every skill folder is listed by an agent;
- no agent has a tool named load_skill, and the skills folder comes with an
  ai-template.yml.

Warnings: hidden files (the build refuses them only if they are committed), and
prompt text that names a skill otherwise than the agent is offered it (app/<name>).
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

SKILLS_DIR = "skills"  # inside .ironflock/
SKILL_FILE = "SKILL.md"
REFERENCES_DIR = "references"

#: Platform skills that apps may list as platform/<name>. None is open yet.
OPEN_PLATFORM_SKILLS: frozenset[str] = frozenset()
#: The tool an agent loads its skills with; no app may name a tool so.
RESERVED_TOOL = "load_skill"

NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
REFERENCE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.md")
MAX_NAME = 64
MAX_DESCRIPTION = 500
MAX_INSTRUCTIONS = 20_000
MAX_REFERENCE = 40_000
MAX_REFERENCES = 20
MAX_REFERENCE_NAME = 64
MAX_FRONTMATTER = 4_000
MAX_SKILL_FILE = MAX_FRONTMATTER + MAX_INSTRUCTIONS + 1_000
MAX_SKILLS = 20
MAX_APP_BYTES = 2 * 1024 * 1024
MAX_LISTED = 20

BOM = "﻿"
TAG = re.compile(r"<\s*/?\s*skill\b", re.IGNORECASE)
DESCRIPTION_WHITESPACE = frozenset("\t\n\r")
ALLOWED = f"a skill folder holds only {SKILL_FILE} and {REFERENCES_DIR}/<file>.md"


def check_skills(ironflock: Path, ai_doc: Any, ai_present: bool, report: Any) -> None:
    """Check .ironflock/skills/ and the agents' `skills` lists.

    ai_doc is the loaded ai-template.yml (a validate.Doc) or None; ai_present
    says whether the file exists, also when it could not be loaded."""
    root = ironflock / SKILLS_DIR
    folders: dict[str, dict[str, str]] = {}  # skill folder -> {relative path: text}
    all_folders: set[str] = set()
    bad_folders: set[str] = set()
    has_folder = root.is_symlink() or root.exists()

    def err(file: str, message: str, path: list | None = None, line: int | None = None) -> None:
        report.at("ERROR", file, line, path or [], message)

    if root.is_symlink():
        err(SKILLS_DIR, "is a symbolic link; the release build refuses it, make it a real folder")
    elif root.exists() and not root.is_dir():
        err(SKILLS_DIR, f"must be a folder of skill folders, {SKILLS_DIR}/<name>/{SKILL_FILE}")
    elif root.is_dir():
        total_bytes = read_files(root, folders, all_folders, report)
        for folder in sorted(all_folders):
            if not NAME.fullmatch(folder) or len(folder) > MAX_NAME:
                err(
                    f"{SKILLS_DIR}/{folder}",
                    "a skill folder is named in lowercase letters and digits, in words joined by "
                    f"single hyphens (e.g. maintenance-playbook), at most {MAX_NAME} characters",
                )
                bad_folders.add(folder)
                folders.pop(folder, None)
        if len(all_folders) > MAX_SKILLS:
            err(SKILLS_DIR, f"the app has {len(all_folders)} skills, at most {MAX_SKILLS}")
        if total_bytes > MAX_APP_BYTES:
            err(
                SKILLS_DIR,
                f"the skill files are {total_bytes} bytes together (UTF-8), at most {MAX_APP_BYTES} (2 MiB)",
            )
        for folder, files in sorted(folders.items()):
            check_skill(folder, files, report)

    if has_folder and not ai_present:
        err(
            SKILLS_DIR,
            "there is no ai-template.yml; add the agent that loads these skills (its `skills` list), "
            "or remove the folder",
        )

    agents = ai_doc.data if ai_doc is not None and isinstance(ai_doc.data, dict) else {}
    readable = not root.is_symlink() and (root.is_dir() or not root.exists())
    listed: set[str] = set()
    for agent_name, agent in agents.items():
        if isinstance(agent, dict):
            check_agent(ai_doc, agent_name, agent, all_folders if readable else None, listed, report)

    if ai_doc is not None:  # a missing or unreadable ai-template.yml is reported already
        for folder in sorted(all_folders - listed - bad_folders):
            err(
                f"{SKILLS_DIR}/{folder}",
                f"no agent lists this skill; add {folder} to the `skills` of an agent in "
                "ai-template.yml, or remove the folder",
            )


def read_files(root: Path, folders: dict, all_folders: set, report: Any) -> int:
    """Collect every file under the skills folder into folders; report the
    files the release build refuses. Returns the files' total size in bytes."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        for name in sorted(dirnames + filenames):
            path = here / name
            rel = path.relative_to(root).as_posix()
            where = f"{SKILLS_DIR}/{rel}"
            if name.startswith("."):
                report.at(
                    "WARN", where, None, [],
                    f"hidden; if it is committed, the release build fails ({ALLOWED}). "
                    "Delete it or keep it out of git",
                )
                continue
            if path.is_symlink():
                report.at("ERROR", where, None, [], "is a symbolic link; the release build refuses it, copy the file in")
                continue
            if path.is_dir():
                continue  # its files are checked one by one
            folder, _, inner = rel.partition("/")
            if not inner:
                report.at(
                    "ERROR", where, None, [],
                    f"not inside a skill folder; each skill is a folder .ironflock/{SKILLS_DIR}/<name>/ with a {SKILL_FILE}",
                )
                continue
            all_folders.add(folder)
            problem = path_problem(inner)
            if problem:
                report.at("ERROR", where, None, [], problem)
                continue
            raw = path.read_bytes()
            total += len(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                report.at("ERROR", where, None, [], "is not valid UTF-8 text; save it as UTF-8")
                continue
            folders.setdefault(folder, {})[inner] = text.removeprefix(BOM)
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and not (here / d).is_symlink())
    for folder in all_folders:
        folders.setdefault(folder, {})
    return total


def path_problem(inner: str) -> str | None:
    """Why the release build refuses a file at <skill>/<inner>, or None."""
    if inner == SKILL_FILE:
        return None
    parts = inner.split("/")
    if len(parts) == 2 and parts[0] == REFERENCES_DIR:
        name = parts[1]
        if not REFERENCE_NAME.fullmatch(name):
            return (
                f"a reference file is named <name>.md, with letters, digits, '.', '_' and '-' "
                f"and starting with a letter or digit; rename it ({ALLOWED})"
            )
        if len(name) > MAX_REFERENCE_NAME:
            return f"the reference file name is {len(name)} characters, at most {MAX_REFERENCE_NAME}"
        return None
    return f"this file is not allowed: {ALLOWED}; scripts, images and other files are refused"


def check_skill(folder: str, files: dict[str, str], report: Any) -> None:
    """One skill folder's SKILL.md and references."""
    file = f"{SKILLS_DIR}/{folder}/{SKILL_FILE}"

    def err(message: str, path: list | None = None, line: int | None = None, where: str = file) -> None:
        report.at("ERROR", where, line, path or [], message)

    if SKILL_FILE not in files:
        err(f"the skill folder has no {SKILL_FILE}", where=f"{SKILLS_DIR}/{folder}")
        return
    text = files[SKILL_FILE]
    if len(text) > MAX_SKILL_FILE:
        err(f"{SKILL_FILE} is {len(text)} characters, at most {MAX_SKILL_FILE}")
        return
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        err(f"{SKILL_FILE} must start with a '---' line, then the frontmatter with name and description", line=1)
        return
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        err("the frontmatter has no closing '---' line", line=1)
        return
    frontmatter = "\n".join(lines[1:end])
    if len(frontmatter) > MAX_FRONTMATTER:
        err(f"the frontmatter is {len(frontmatter)} characters, at most {MAX_FRONTMATTER}", line=2)
        return
    try:
        meta = yaml.safe_load(frontmatter)  # the release build reads it with YAML 1.1 rules
        node = yaml.compose(frontmatter, Loader=yaml.SafeLoader)
    except Exception as exc:
        mark = getattr(exc, "problem_mark", None)
        problem = getattr(exc, "problem", None) or "it cannot be read"
        err(f"the frontmatter is not valid YAML: {problem}", line=mark.line + 2 if mark else 2)
        return
    if not isinstance(meta, dict):
        err("the frontmatter must be a mapping with name and description", line=2)
        return

    def line_of(key: str) -> int:
        if isinstance(node, yaml.MappingNode):
            for k, _ in node.value:
                if k.value == key:
                    return k.start_mark.line + 2
        return 2

    name, description = meta.get("name"), meta.get("description")
    if not isinstance(name, str):
        err("the frontmatter needs `name` as a string, the folder's name", ["name"], line_of("name"))
    elif name.strip() != folder:
        err(f"name {name.strip()!r} differs from the folder's name {folder!r}; they must be equal", ["name"], line_of("name"))
    if not isinstance(description, str):
        err(
            "the frontmatter needs `description` as a string: what the skill is for and when to load it",
            ["description"],
            line_of("description"),
        )
    else:
        description = description.strip()
        at = line_of("description")
        if not description:
            err("the description is empty; say what the skill is for and when to load it", ["description"], at)
        elif len(description) > MAX_DESCRIPTION:
            err(f"the description is {len(description)} characters, at most {MAX_DESCRIPTION}", ["description"], at)
        bad = next(
            (c for c in description if unicodedata.category(c) in ("Cc", "Cf") and c not in DESCRIPTION_WHITESPACE),
            None,
        )
        if bad is not None:
            err(f"the description contains the invisible character U+{ord(bad):04X}; remove it", ["description"], at)
        if TAG.search(description):
            err("the description contains a <skill> tag, which the release build refuses; write it differently", ["description"], at)

    instructions = "\n".join(lines[end + 1 :]).strip()
    body = end + 2  # the first line after the frontmatter
    if not instructions.replace(BOM, "").strip():
        err("there are no instructions after the frontmatter", ["instructions"], body)
    elif len(instructions) > MAX_INSTRUCTIONS:
        err(
            f"the instructions are {len(instructions)} characters, at most {MAX_INSTRUCTIONS}; "
            f"move parts into {REFERENCES_DIR}/<file>.md",
            ["instructions"],
            body,
        )
    if TAG.search(instructions):
        err("the instructions contain a <skill> tag, which the release build refuses; write it differently", ["instructions"], body)

    references = sorted(p for p in files if p != SKILL_FILE)
    if len(references) > MAX_REFERENCES:
        err(
            f"the skill has {len(references)} reference files, at most {MAX_REFERENCES}",
            where=f"{SKILLS_DIR}/{folder}/{REFERENCES_DIR}",
        )
    for ref in references:
        ref_text = files[ref]
        where = f"{SKILLS_DIR}/{folder}/{ref}"
        if not ref_text.replace(BOM, "").strip():
            err("the reference file is empty", where=where)
        elif len(ref_text) > MAX_REFERENCE:
            err(f"the reference file is {len(ref_text)} characters, at most {MAX_REFERENCE}; split it", where=where)
        if TAG.search(ref_text):
            err("the reference file contains a <skill> tag, which the release build refuses; write it differently", where=where)


def check_agent(doc: Any, agent_name: str, agent: dict, folders: set[str] | None, listed: set[str], report: Any) -> None:
    """One agent's `skills` list, its tools, and how its prompt names skills.
    folders is None when the skills folder could not be read (reported already)."""
    tools = agent.get("tools")
    if isinstance(tools, dict) and RESERVED_TOOL in tools:
        report.error(
            doc,
            [agent_name, "tools", RESERVED_TOOL],
            f"the tool name {RESERVED_TOOL} is reserved for loading skills; give the tool another name",
        )

    entries = agent.get("skills")
    if not isinstance(entries, list):
        entries = []
    if len(entries) > MAX_LISTED:
        report.error(doc, [agent_name, "skills"], f"the agent lists {len(entries)} skills, at most {MAX_LISTED}")
    seen: set[str] = set()
    own: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, str):
            continue
        path = [agent_name, "skills", i]
        if entry in seen:
            report.error(doc, path, f"{entry!r} is listed twice")
            continue
        seen.add(entry)
        if entry.startswith("app/"):
            bare = entry[len("app/") :]
            listed.add(bare)
            report.error(
                doc,
                path,
                f"list the app's own skill by its folder name, without 'app/': {bare}. "
                "The agent is offered it as app/<name>, the form its prompt uses",
            )
        elif entry.startswith("project/"):
            report.error(doc, path, f"{entry!r} names a project skill, which an app cannot list")
        elif entry.startswith("platform/"):
            name = entry[len("platform/") :]
            if name not in OPEN_PLATFORM_SKILLS:
                offered = ", ".join(sorted(OPEN_PLATFORM_SKILLS)) or "none at the moment"
                report.error(
                    doc,
                    path,
                    f"{entry!r} is not a platform skill that apps can use (open to apps: {offered}); "
                    "the release build fails",
                )
        elif NAME.fullmatch(entry) and len(entry) > MAX_NAME:
            report.error(doc, path, f"the skill name is {len(entry)} characters, at most {MAX_NAME}")
        elif NAME.fullmatch(entry):
            listed.add(entry)
            own.add(entry)
            if folders is not None and entry not in folders:
                report.error(
                    doc,
                    path,
                    f"there is no skill folder .ironflock/{SKILLS_DIR}/{entry}/ with a {SKILL_FILE}; "
                    "create it, or remove the entry",
                )
        else:
            report.error(
                doc,
                path,
                f"{entry!r} is not a skill name: the app's own skills by their folder name (lowercase "
                "letters and digits joined by single hyphens), platform skills as platform/<name>",
            )

    # The agent is offered its app's skills as app/<name>: prompt text has to use that form.
    for key in ("system_prompt", "tool_description"):
        text = agent.get(key)
        if not isinstance(text, str):
            continue
        for name in sorted(own):
            if "-" in name and re.search(rf"(?<![\w/-]){re.escape(name)}(?![\w-])", text):
                report.warn(
                    doc,
                    [agent_name, key],
                    f"names the skill {name} without its prefix; the agent is offered it as app/{name}, so write that",
                )
        for name in sorted(set(re.findall(r"(?<![\w/])app/([a-z0-9]+(?:-[a-z0-9]+)*)", text)) - own):
            report.warn(
                doc,
                [agent_name, key],
                f"mentions app/{name}, but this agent does not list {name} in its skills, so it cannot load it",
            )
