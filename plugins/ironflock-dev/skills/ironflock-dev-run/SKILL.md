---
name: ironflock-dev-run
description: Use in the hosted IronFlock IDE for requests about the current app’s development run, including “build the app”, “show the app logs”, “show the build logs”, “start the app” and “is it running?”. Builds the IDE working copy on a development device and checks its DEV stage through IronFlock MCP.
metadata:
  mcp-tools: list_my_apps get_app_repository list_dev_devices build_dev_app list_builds get_build set_app_state get_app_logs check_app_status
---

# Work with the development run

In the hosted IDE, the folder directly below `~/apps` identifies the app, even
when the editor opens a subdirectory. Use the workspace's app-scoped IronFlock
MCP connection. Resolve its `app_key` with `list_my_apps`. Use
`list_dev_devices` to find the device and its project (`swarm_key`). Honor a
target the user already selected. For a build use an online device the user may
develop on. For runtime logs use the device with the relevant DEV run. If
several targets fit, ask which device and give their names. If the selected
device is offline, report that.

- **Build the app.** Check the working copy with `get_app_repository`. Call
  `build_dev_app` with the app and device keys. Omit `branch` and `commit`
  for the IDE working copy, including uncommitted files. Supply a repository
  revision only when requested. For a pending build, follow its `build_key`
  with `get_build`. If the submission times out, look up the DEV build before
  considering a retry. Report the outcome and the relevant error if it fails.
- **The cloud IDE must run.** The working copy exists only in the hosted
  IDE. The platform builds it, and shows its development board, only while
  that IDE runs; `get_app_repository` reports this as `ide_running`. If the
  platform refuses because the cloud IDE is not running, do not retry: pass
  on its sentence. The user opens the app in DevStudio, or builds a pushed
  branch or commit. A checkout outside the hosted IDE, such as one on a
  laptop, is never built as a working copy: build its pushed branch.
- **Read build logs.** Use `get_build` for the relevant build key. If the key
  is unknown, use `list_builds` with `kind: "DEV"` and the target device.
- **Read app logs.** Call `get_app_logs` with `app_key`, `swarm_key`,
  `device_keys: [device_key]` and explicit `stage: "DEV"`. Explain what the
  output shows. If there is no development run or its log is empty, say so.
- **Check whether it runs.** Call `check_app_status` with the app and project
  keys and explicit `stage: "DEV"`. Report the selected device's state.
- **Start or stop.** A successful development build leaves the app stopped.
  When asked to start or stop it, use `set_app_state` with explicit
  `stage: "DEV"` and only the selected device.

Local editing, tests and template validation belong in the workspace. Building
an image locally or accessing an installed release requires an explicit request.
If the workspace MCP server or a required DEV operation is unavailable, tell
the user what is missing.
