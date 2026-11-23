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
  and explains which permissions a sign-in or API key grants.
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
  It also knows the figures of ISO 22400, technical availability by VDI
  3423, packaging lines with PackML states, semiconductor tools with SEMI
  E10 states, failures and reliability, energy from meters, and control
  charts and capability.
- `ironflock-cli`: works on a machine with the `ironflock` command: installs
  the device agent, connects the machine as a new device, checks it. It needs
  a shell on that machine, so it is for Claude Code.
- `ironflock-dev-moved`: tells you that the skills to build apps and widgets
  are in the plugin `ironflock-dev`.

The skills start on their own when you ask about these things.

## Set up

Sign in to the IronFlock installation you want to use. It must support browser sign-in for MCP. Each person reviews the client, callback, scopes and project or app restriction in the issuing Studio.

**Claude Code.** Add the marketplace and install the cloud plugin:

```text
/plugin marketplace add IronFlock/agent-skills
/plugin install ironflock@ironflock
```

Reload plugins or restart Claude Code, open `/mcp`, choose the IronFlock cloud server and authenticate. It connects to `https://api.ironflock.com/mcp` without plugin settings. Ask Claude to list your cloud projects.

**Direct appliance connection.** In Claude Code, also install `/plugin install ironflock-appliance@ironflock`. Set **Appliance MCP address** to the full HTTPS endpoint, for example `https://api.plant.example/mcp`. Reload the plugins, select the appliance in `/mcp` and sign in with the appliance account. This works from a computer on the company network. The cloud and appliance have independent connections.

**Claude chat and Cowork.** Use the **Connectors** tab of the IronFlock plugin to connect and sign in. For a custom connector, use **Customize → Connectors**, the full MCP URL, **Sign in now** and **Use Claude’s published identity**. Organization owners can make connectors available to members, who sign in individually. For direct appliance access, Anthropic’s connector service needs to reach the appliance. If your installation supports access through the cloud, choose a paired online appliance whose owner has enabled it instead. [Claude custom connector instructions](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)

**Updating from 1.x.** After updating, sign in through the cloud connection. If you used a custom appliance address, install the appliance plugin and enter the full endpoint there. The old API key and base-address settings are unused. Revoke the old key in Studio once you have verified that other clients do not need it. Keys remain available for scripts and manually configured clients.

## Data

- The cloud connection sends MCP requests to IronFlock’s cloud API. A direct appliance connection sends them to the configured appliance endpoint. When an appliance is accessed through the cloud, its requests and results pass through the cloud.
- Each connected client receives its own access and refresh tokens. The grant is limited by the IronFlock account, scopes, and project or app restriction. End it under **Account Settings → Developer → App sign-ins** in the issuing Studio.
- The tool results Claude reads become part of your conversation. These may include project and device names, logs, alarms, audit entries, SQL results, and app files. Changing tools can install or remove apps, change devices, alarms or transforms, and run device operations. Claude names the instance and asks for confirmation before a change.
- Enter credentials only at the instance’s sign-in or in a separately configured client’s secret settings. The plugin does not ask for keys or tokens in chat.
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
