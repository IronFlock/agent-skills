# IronFlock

Operate your IronFlock instance from Claude: ask which devices are online and
what runs on them, find out why a device or an app does not work, get answers
and production figures from your project's data, and connect new machines.

IronFlock is a platform for fleets of edge devices. It runs apps on the
devices, collects their data in a project database and shows it on boards.
It runs in the cloud or as an appliance on a company's own server; the plugin
works with both.

## What you can ask

- "Which devices in project Plant North are offline, and since when?"
- "Why does the vibration app on press-3 send no data?"
- "What was the average spindle temperature per shift last week?"
- "What is the OEE of line 2 this month, and which stops cost us most?"
- "Update the camera app on all devices of this project."
- "Send me an email when the oil temperature of a press goes above 90 °C."
- "Connect this machine as a new device in project Test." (Claude Code)

Claude reads first and asks before it changes anything: installing, updating,
stopping or removing an app, creating or deleting a device, an alarm or a
transform. For an app that costs money it shows the price before it asks.

## Skills

- `ironflock-connect`: connects Claude to IronFlock, checks the connection,
  and explains what an API key lets Claude do.
- `ironflock-fleet`: devices, the apps on them, alarms, logs and the audit
  log; finds out why something does not work, and changes apps, devices and
  alarms with your agreement.
- `ironflock-data`: finds a project's tables, queries the project database
  (PostgreSQL with TimescaleDB) with read-only SQL, reads the files apps
  store, and saves transforms that keep a derived figure live for boards.
- `ironflock-production-figures`: OEE with availability, performance and
  quality shown apart, stops and downtime ranked by minutes and by count,
  losses, and why a machine stopped. It asks for what the data does not hold,
  such as the planned time or the ideal cycle time, instead of assuming it.
- `ironflock-cli`: works on a machine with the `ironflock` command: installs
  the device agent, connects the machine as a new device, checks it. It needs
  a shell on that machine, so it is for Claude Code.
- `ironflock-dev-moved`: tells you that the skills to build apps and widgets
  are in the plugin `ironflock-dev`.

The skills start on their own when you ask about these things.

## Set up

You need an IronFlock account and an API key.

1. In IronFlock Studio, open **Account Settings** > **Developer** >
   **API keys** and choose **Create API key**. Choose what the key may do
   (read only by default) and where (all your projects, some of them, or one
   app), then choose **Copy API key**. Studio shows the key only once. It is
   valid for one year.
2. Give the key to Claude in its settings, never in a chat message.

**Claude Code** (terminal, IDE extensions, the desktop app's Code tab). Add
the plugin from Claude's plugin directory, or from IronFlock's marketplace:

```text
/plugin marketplace add IronFlock/agent-skills
/plugin install ironflock@ironflock
```

Claude Code then asks for two settings:

- **IronFlock API address**: keep `https://api.ironflock.com` for IronFlock
  in the cloud. For an appliance enter `https://api.<your appliance's domain>`,
  without `/mcp` and without a slash at the end.
- **IronFlock API key**: the key from Studio.

Restart Claude Code. `/mcp` then shows the IronFlock server as connected.
`/plugin configure ironflock@ironflock` changes the two settings later; a
plugin added from the directory is named `ironflock@synced` there.

**The Claude app** (chat on the web, on the desktop and on a phone, and
Cowork). The skills work there, but these apps do not ask for the plugin's
two settings, so they do not use the plugin's own connection. Add IronFlock
as a custom connector instead, under **Customize > Connectors**: the URL
`https://api.ironflock.com/mcp` (for an appliance, its API address followed
by `/mcp`), authentication **No sign-in**, and the request header
`authorization` with the value `Bearer <your API key>`. Request headers on
custom connectors are a beta that not every organization has; without them,
use Claude Code. A connector connects from Anthropic's servers, so an
appliance that only your company network reaches cannot be connected this
way, while Claude Code on a computer in that network can. Ask Claude to
"connect to IronFlock" and
`ironflock-connect` takes you through each step and what to do when one
fails.

Then ask Claude to list your IronFlock projects.

## Requirements

- An IronFlock instance with the IronFlock API service 2.0.0 or later.
  IronFlock in the cloud has it. An appliance has it from IronFlock 1.6.66 on.
- An API key of that instance. A read-only key is enough to look at a fleet
  and to query its data. Claude can change something only with a key that
  allows it, and never more than the key's owner may do in IronFlock.
- For `ironflock-cli`: Claude Code on the machine to set up, or on a computer
  that reaches it over SSH, and the
  [`ironflock` command](https://ironflock.com/docs/app-development/cli/).

## Data

What the plugin sends, runs and fetches:

- **It talks to one server: the IronFlock API address you set.** That is
  `https://api.ironflock.com` unless you enter your appliance's address.
  Claude calls IronFlock's MCP tools there, and every request carries your
  API key in the `Authorization` header. The plugin sends nothing to any
  other server.
- **What Claude reads becomes part of your conversation**: the names and
  states of projects, devices and apps, log lines, alarms, audit log entries,
  the results of SQL queries on your project database, and files your apps
  stored. Which of these Claude can read is set by the key's scopes.
- **What Claude can change on the instance**, with a key that allows it and
  after your yes: install, update, start, stop and remove apps; create and
  delete devices; create, change and delete alarms and transforms; call the
  tools that apps bring, which run on devices.
- **The API key** is entered in Claude Code's plugin dialog, which keeps it
  in the system's secure credential store. The skills tell Claude never to
  ask for a key in the chat, and not to use or repeat one that is pasted
  there.
- **Commands.** The plugin holds no scripts, hooks or programs; its files are
  Markdown. Only `ironflock-cli` has Claude run something: the `ironflock`
  command, in your shell, with Claude Code's usual permission prompts. That
  command can install the device agent on a machine (this needs root) and,
  with `--host`, run on another machine over SSH. Claude asks before each
  such change and names the machine. The plugin does not install the
  `ironflock` command itself; you do, with the line on IronFlock's
  installation page.

## Help

- [IronFlock documentation](https://ironflock.com/docs/)
- [Questions and problems](https://github.com/IronFlock/agent-skills/issues)
- [What each version changed](https://github.com/IronFlock/agent-skills/blob/main/CHANGELOG.md)
- [Privacy](https://ironflock.com/en/company-legal/terms-privacy/): IronFlock's
  terms and privacy notice

## License

MIT, see
[LICENSE](https://github.com/IronFlock/agent-skills/blob/main/LICENSE).

Three references of `ironflock-production-figures` incorporate material
adapted from the claude-for-manufacturing plugin by Anthropic and are under
the Apache License, Version 2.0. Each says so at its top. The licence text
and the notice of what was changed are in that skill's folder
(`skills/ironflock-production-figures/LICENSE-APACHE-2.0.txt` and `NOTICE`).
