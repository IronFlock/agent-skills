#!/usr/bin/env python3
"""Grade one iteration of the ironflock-data skill evals.

    python3 evals/data/grade.py prompts <iteration-dir>   print the prompts, filled in
    python3 evals/data/grade.py grade <iteration-dir>     score the runs

The evals run against a local IronFlock with its demo data, connected over
MCP, never against a real instance. The project they use needs an app that
writes a numeric reading as a time series from at least one device, with
data in the last 30 days, and no data about compressors or oil pressure.
Write the names into <iteration-dir>/placeholders.json (the keys are under
"placeholders" in evals.json).

Run the prompts as described in evals/fleet/grade.py, with the same MCP
configuration (evals/fleet/mcp.json); with_skill loads the plugin from this
checkout. The checks, on the tool calls, the SQL the agent ran and patterns on
the reply, come from evals/fleet/transcript.py; read the replies too.

Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fleet"))

from transcript import (  # noqa: E402
    AGGREGATE,
    TIME_BOUND,
    Run,
    aggregated_or_small,
    asks_to_confirm,
    called,
    changes_nothing,
    check,
    main,
    names,
    not_called,
    only_known_tables,
    row_limit,
    said,
    schema_first,
    sql_of,
    time_bounded,
)

HERE = Path(__file__).resolve().parent
EVALS = json.loads((HERE / "evals.json").read_text(encoding="utf-8"))
BY_DAY = re.compile(r"time_bucket\s*\(\s*'(1 day|24 hours|1d)'|date_trunc\s*\(\s*'day'|::\s*date\b|\bdate\s*\(|\bcast\s*\([^)]*\bas\s+date\)", re.I)
GROUP_BY = re.compile(r"\bgroup\s+by\b", re.I)
NEWEST = re.compile(r"distinct\s+on|\blast\s*\(|row_number\s*\(|max\s*\(\s*\"?tsp|rank\s*\(", re.I)
RATIO = re.compile(r"\bfilter\s*\(\s*where|\bcase\s+when|\bavg\s*\(\s*\(?.*>|::\s*int", re.I)
SCHEMA_ID = re.compile(r"databackend_\d+")


def queries(run: Run) -> list[str]:
    return [sql_of(c) for c in run.of("execute_sql")]


def any_query(run: Run, text: str, *patterns: re.Pattern) -> dict:
    hits = [q for q in queries(run) if all(p.search(q) for p in patterns)]
    return check(text, hits, (hits[0][:160] if hits else f"{len(queries(run))} query(ies), none matches"))


def grade_data_overview(run: Run, v: dict) -> list[dict]:
    ids = SCHEMA_ID.findall(run.reply)
    return [
        called(run, "get_schema"),
        names(run.reply, "the app", v["app"]),
        check("keeps internal schema names out of the answer", not ids, ", ".join(sorted(set(ids))) or "none"),
        aggregated_or_small(run, most=20),
    ]


def grade_daily_average(run: Run, v: dict) -> list[dict]:
    return [
        schema_first(run),
        only_known_tables(run),
        any_query(run, "aggregates per day and device in one query", AGGREGATE, BY_DAY, GROUP_BY, TIME_BOUND),
        time_bounded(run),
        aggregated_or_small(run),
        names(run.reply, "the device by name", v["device"]),
        check("states the time range or the time zone", *said(run.reply, r"\butc\b|time ?zone|last 7 days|past 7 days|\d{4}-\d{2}-\d{2}")),
    ]


def grade_missing_data(run: Run, v: dict) -> list[dict]:
    absent = (
        r"\b(no|not|isn't|doesn't|don't|cannot find|can't find|couldn't find|could not find|none)\b[^.]{0,100}\b(oil|pressure|compressors?)\b"
        r"|\b(oil|pressure|compressors?)\b[^.]{0,100}\b(no|not|isn't|doesn't|don't|none)\b"
    )
    return [
        called(run, "get_schema"),
        only_known_tables(run),
        check("says the project holds no such data", *said(run.reply, absent)),
        check("names what the project does hold", *said(run.reply, re.escape(v["app"]) + "|" + re.escape(v["quantity"]))),
    ]


def grade_current_values(run: Run, v: dict) -> list[dict]:
    return [
        schema_first(run),
        only_known_tables(run),
        any_query(run, "reads the newest value per device", NEWEST),
        time_bounded(run),
        called(run, "list_devices"),
        names(run.reply, "the device by name", v["device"]),
    ]


def grade_raw_export(run: Run, v: dict) -> list[dict]:
    paged = [q[:120] for q in queries(run) if re.search(r"\boffset\s+\d", q, re.I)]
    big = [c for c in run.of("execute_sql") if not AGGREGATE.search(sql_of(c)) and row_limit(c) > 100]
    return [
        check("does not page through the history", not paged and len(queries(run)) <= 3, f"{len(queries(run))} queries, {len(paged)} with OFFSET"),
        check("pulls no large raw result", not big, f"{len(big)} raw query(ies) over 100 rows"),
        check("explains the result limit", *said(run.reply, r"1[,.]?000|\blimit|too (many|large|big)|\bcut\b|at most")),
        check("points to the download in Studio's query console", *said(run.reply, r"query console|download|\bcsv\b")),
        check("gives the query to run there", *said(run.reply, r"\bselect\b[\s\S]{0,600}\bfrom\b")),
    ]


def grade_count_yesterday(run: Run, v: dict) -> list[dict]:
    counting = re.compile(r"\bcount\s*\(", re.I)
    return [
        schema_first(run),
        only_known_tables(run),
        any_query(run, "counts per device in one bounded query", counting, GROUP_BY, TIME_BOUND),
        not_called(run, "save_transform"),
        changes_nothing(run),
    ]


def grade_latest_not_transform(run: Run, v: dict) -> list[dict]:
    return [
        not_called(run, "save_transform"),
        check("names the widget's latest setting", *said(run.reply, r"\blatest\b")),
        check("says a transform shows it late (on its schedule)", *said(run.reply, r"schedule|refresh|every \d+ minutes|delay|\blag|not live|late")),
        changes_nothing(run),
    ]


def grade_kpi_transform(run: Run, v: dict) -> list[dict]:
    return [
        schema_first(run),
        only_known_tables(run),
        any_query(run, "tests the SELECT first, bounded and grouped", RATIO, GROUP_BY, TIME_BOUND),
        not_called(run, "save_transform"),
        check("proposes a name for the transform", *said(run.reply, r"\bname[ds]?\b|\bcalled\b|`[a-z][a-z0-9_]+`")),
        asks_to_confirm(run.reply),
        changes_nothing(run),
    ]


GRADERS = {
    "data-overview": grade_data_overview,
    "daily-average": grade_daily_average,
    "missing-data": grade_missing_data,
    "current-values": grade_current_values,
    "raw-export": grade_raw_export,
    "count-yesterday": grade_count_yesterday,
    "latest-not-transform": grade_latest_not_transform,
    "kpi-transform": grade_kpi_transform,
}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], EVALS, GRADERS, __doc__))
