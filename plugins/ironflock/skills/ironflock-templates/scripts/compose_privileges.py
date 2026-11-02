"""Privileged settings in an app's docker-compose.yml, for validate.py.

An app that uses privileged settings must declare `privileged.reason` in its
data-template.yml: the platform refuses to publish it otherwise, and without the
project's grant the device agent removes these settings before it starts the
app. The platform and the device agent classify a compose file with the same
rules, pinned by a shared fixture of test vectors (a copy is in this skill's
tests/privileged-compose-fixture.json); this is the same classifier in Python.

classify(compose) returns the privileged settings as
`{"service", "feature", "value"}` dicts, in the platform's order: services by
name, within a service by SERVICE_KEYS, within a list in list order, then the
top-level volumes, networks, secrets and configs by name, and include
(service "").
"""

from __future__ import annotations

import json
import re
from typing import Any

SERVICE_KEYS = (
    "privileged",
    "cap_add",
    "devices",
    "device_cgroup_rules",
    "security_opt",
    "network_mode",
    "pid",
    "ipc",
    "uts",
    "userns_mode",
    "cgroup",
    "cgroup_parent",
    "volumes",
    "volumes_from",
    "extends",
)
NAMESPACE_KEYS = {"network_mode", "pid", "ipc", "uts", "userns_mode", "cgroup"}
DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
TIME_FILES = {"/etc/localtime", "/etc/timezone"}


def text(value: Any) -> str:
    """Strings as written, anything else JSON-encoded the way the platform does (compact)."""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)  # true, false, null, numbers


def truthy(value: Any) -> bool:
    """external and name as the platform reads them: null, false, 0 and "" are false; any mapping or list is true."""
    if value is None or isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return True


def entries(value: Any) -> list:
    """A list key's entries. A scalar where compose wants a list counts as one entry."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def leaves_dir(path: str) -> bool:
    return ".." in re.split(r"[\\/]", path)


def host_source(source: Any, read_only: bool) -> bool:
    """Whether a bind source reaches the host outside the compose directory."""
    if not isinstance(source, str):
        return False
    if "$" in source:
        return True
    if source.startswith(("/", "~", "\\")) or DRIVE.match(source):  # \\ = UNC path, named pipe
        return not (source in TIME_FILES and read_only)
    if source.startswith("."):
        return leaves_dir(source)
    return False  # a named volume


def short_volume(entry: str) -> bool:
    """source:target[:mode], the mode being everything after the second colon."""
    drive = entry[:2] if DRIVE.match(entry) else ""
    parts = entry[len(drive):].split(":", 2)
    if len(parts) == 1:
        return "$" in entry  # an anonymous volume, unless a parameter fills it in
    mode = parts[2] if len(parts) > 2 else ""
    return host_source(drive + parts[0], "ro" in mode.split(","))


def long_volume(entry: dict) -> bool:
    kind, source = entry.get("type"), entry.get("source")
    if kind == "bind":
        return host_source(source, entry.get("read_only") is True)
    if kind == "npipe":
        return True
    if kind == "volume":
        return isinstance(source, str) and "$" in source
    return False


def outside_file(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    return path.startswith(("/", "~", "\\")) or bool(DRIVE.match(path)) or "$" in path or leaves_dir(path)


def service_features(service: dict) -> list[tuple[list, str, str]]:
    """(path below the service, feature, value) for one service."""
    found = []
    for key in SERVICE_KEYS:
        if key not in service:
            continue
        value = service[key]
        if key == "privileged":
            if value is not None and value is not False and value != "false":  # null = unset
                found.append(([key], key, "true" if value is True else text(value)))
        elif key in ("cap_add", "device_cgroup_rules"):
            found += [([key, i], key, text(e)) for i, e in enumerate(entries(value))]
        elif key == "devices":
            for i, e in enumerate(entries(value)):
                source = e.get("source") if isinstance(e, dict) else None
                found.append(([key, i], key, source if isinstance(source, str) else text(e)))
        elif key == "security_opt":
            for i, e in enumerate(entries(value)):
                if not text(e).startswith("no-new-privileges"):
                    found.append(([key, i], key, text(e)))
        elif key in NAMESPACE_KEYS:
            mode = text(value)
            if mode == "host" or mode.startswith("container:") or "$" in mode:
                found.append(([key], key, mode))
        elif key == "cgroup_parent":
            if value is not None and value != "":  # any parent cgroup is a place in the host's hierarchy
                found.append(([key], key, text(value)))
        elif key == "volumes":
            for i, e in enumerate(entries(value)):
                if isinstance(e, str) and short_volume(e):
                    found.append(([key, i], key, e))
                elif isinstance(e, dict) and long_volume(e):
                    source = e.get("source")
                    found.append(([key, i], key, source if isinstance(source, str) else ""))
        elif key == "volumes_from":
            for i, e in enumerate(entries(value)):
                if isinstance(e, str) and e.startswith("container:"):
                    found.append(([key, i], key, e))
        elif key == "extends":
            # Another file can hold any setting, and is not part of the release.
            if isinstance(value, dict) and isinstance(value.get("file"), str):
                found.append(([key, "file"], key, value["file"]))
    return found


def mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def classify_with_paths(compose: Any) -> list[tuple[list, dict]]:
    """Like classify, with each setting's path in the compose file."""
    compose = mapping(compose)
    found: list[tuple[list, dict]] = []
    services = mapping(compose.get("services"))
    for name in sorted(services):
        service = services[name]
        if isinstance(service, dict):
            for path, feature, value in service_features(service):
                found.append((["services", name, *path], {"service": name, "feature": feature, "value": value}))

    def top(path: list, feature: str, key: str) -> None:
        found.append((path, {"service": "", "feature": feature, "value": key}))

    volumes = mapping(compose.get("volumes"))
    for key in sorted(volumes):
        volume = mapping(volumes[key])
        if volume.get("driver_opts"):
            top(["volumes", key, "driver_opts"], "volume_driver_opts", key)
        if truthy(volume.get("external")) or truthy(volume.get("name")):
            top(["volumes", key], "volume_external", key)
    networks = mapping(compose.get("networks"))
    for key in sorted(networks):
        network = mapping(networks[key])
        driver = network.get("driver")
        own_driver = driver is not None and driver != "" and driver != "bridge"  # macvlan, ipvlan, host
        if own_driver or network.get("driver_opts"):
            top(["networks", key, "driver" if own_driver else "driver_opts"], "network_driver", key)
        if truthy(network.get("external")) or truthy(network.get("name")):
            top(["networks", key], "network_external", key)
    for section, feature in (("secrets", "secret_file"), ("configs", "config_file")):
        items = mapping(compose.get(section))
        for key in sorted(items):
            if outside_file(mapping(items[key]).get("file")):
                top([section, key, "file"], feature, key)
    # An included file can hold any setting, and is not part of the release.
    include = compose.get("include")
    for i, entry in enumerate(entries(include)):
        value = text(entry.get("path")) if isinstance(entry, dict) else text(entry)
        top(["include", i] if isinstance(include, list) else ["include"], "include", value)
    return found


def classify(compose: Any) -> list[dict]:
    return [feature for _, feature in classify_with_paths(compose)]
