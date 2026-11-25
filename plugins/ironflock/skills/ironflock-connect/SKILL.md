---
name: ironflock-connect
description: Connect Claude Code, Claude chat or Cowork to IronFlock through browser sign-in. Use for cloud or appliance setup, connector authentication and scope changes, API-key alternatives, connection failures or choosing which instance to operate.
metadata:
  mcp-tools: list_projects list_devices
  min-api-version: 2.2.0
---

# Connect Claude to IronFlock

Establish which Claude surface the person uses, which IronFlock installation they mean, and whether they want a direct connection or a cloud connection to a paired appliance. If the request already specifies these, use them. The plugin signs each person in to their own IronFlock account. They review the requesting client, callback, permissions and project or app restrictions in Studio.

## Claude Code

For the cloud, enter these commands in Claude Code:

```text
/plugin marketplace add IronFlock/ai-plugins
/plugin install ironflock@ironflock
```

Reload plugins or restart Claude Code. Open `/mcp`, select the IronFlock cloud server and authenticate. The server address is fixed at `https://api.ironflock.com/mcp`. Approve the read scopes in the browser to look at projects and devices. The basic plugin has no setup fields.

For a direct appliance connection, install `/plugin install ironflock-appliance@ironflock` as well. Enter its full HTTPS MCP address, such as `https://api.plant.example/mcp`, in **Appliance MCP address**. Reload plugins, select the appliance connection in `/mcp` and sign in to that appliance using its local account. Use `/plugin configure ironflock-appliance@ironflock` to change the address. A company network or VPN is sufficient when this computer can reach the appliance. If its certificate is untrusted, ask its administrator for the company certificate authority and the installation instructions.

## Claude chat and Cowork

Open the IronFlock plugin’s **Connectors** tab, choose the cloud server and connect. The person signs in and reviews the grant in Studio. If a custom connector is needed, use **Customize → Connectors → Add custom connector**, the full MCP URL, **Sign in now** and **Use Claude’s published identity**. The cloud URL is `https://api.ironflock.com/mcp`. A Team or Enterprise owner or authorized administrator can make the connector available in **Organization settings → Connectors**. Each member connects their own IronFlock account. Enable the connector for the conversation.

For a direct appliance connector use `https://api.<appliance-domain>/mcp` and sign in there. Chat and Cowork remote connectors run from Anthropic’s servers. For a private appliance, choose a paired appliance through the cloud when cloud MCP access is on, or use Claude Code inside the appliance’s network. See [Anthropic’s custom connector instructions](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp).

## Select and verify the instance

Use the connected server’s list of instances if it offers one. For a cloud project, call the cloud connection and omit `instance`. To work through the cloud on a paired appliance, select its returned instance identifier (a positive decimal string). Check that the appliance is online and allows cloud access, then pass its identifier on every project lookup, read and change. On a direct appliance connection omit `instance`. An omitted selector, or `"local"`, means the installation the connection is signed in to. Project and device keys belong to that installation. If the connection lacks instance selection, use a direct signed-in connection. Name the selected installation to the person, and ask when more than one target fits.

Cloud MCP forwarding defaults to On, including after upgrades with no saved setting. Older releases default to Off. Use the appliance’s reported `cloud_access` value. The appliance administrator can switch forwarding on or off under **License** in appliance Studio. On releases with remote settings, the paired administrator can also open **Account settings → Instances → Cloud MCP access** in cloud Studio while the appliance is online. For an owned appliance, open its actions menu. In cloud consent or API-key settings, select projects under that appliance’s name. **All projects** reaches the projects the paired local account may use on enabled appliances. Studio can close after setup. If a write loses its response, check the affected state on the selected appliance before repeating it.

Call `list_projects` on that same target, then `list_devices` for the requested project if the person asked about devices. A project restriction can legitimately return an empty list. When multiple connections offer the same tools, keep all calls on the chosen connection.

## Connection problems

- **401 or sign-in expired.** Open the chosen connection and sign in again. Each sign-in is valid only on the instance that issued it. The person can end it under **Account Settings → Developer → App sign-ins** in that instance’s Studio.
- **403 with `insufficient_scope`.** Name the action and the additional permission it needs. In Claude Code, use `/mcp` to authenticate again and review the requested scopes. In chat or Cowork, follow the connector’s reauthorization prompt when offered. Respect a refusal. After consent retry a requested read; before a change, confirm its exact target and check whether it already happened.
- **A project is outside the grant, the appliance is offline, or access through the cloud is switched off.** Report the reason the server gave. A wider scope cannot grant an account access it lacks.
- **429.** Wait for the server’s retry interval, then use fewer requests at once. Keep the existing sign-in or key.
- **Discovery or network error.** Check the exact HTTPS address including one `/mcp`, that the instance offers OAuth discovery, that the client can reach it, and that the certificate is trusted. A 503 or 504 can be temporary. A timeout while changing something calls for a state check before retrying.

## Existing installs and API keys

After updating from 1.x, sign in through the cloud connector. If the old address was an appliance, install and configure the optional appliance plugin. The old key and address settings no longer apply. Once the person has verified that a key is unused elsewhere, they can revoke it in the issuing Studio.

If the person explicitly wants a key for a separate MCP client or script, create one in the target instance’s **Account Settings → Developer → API keys**. Select the smallest scopes and project or app restriction needed. The person enters it themselves into that client’s secret storage and enables a Bearer Authorization header. Never request a key in chat or write one to a command, project file or transcript. If they paste a key, do not repeat, store or use it. Explain that it was disclosed and ask them to revoke it in Studio. A manually configured client receiving 401 should check expiry or revocation in Studio before replacing its key. OAuth sign-in needs no fixed request headers.

## Permissions

An IronFlock sign-in or API key carries scopes, each of which allows one area to be read
or changed:

| Scope | Allows |
|---|---|
| `devices:read`, `devices:write` | read the devices and projects; create and delete devices |
| `apps:read`, `apps:write` | read the installed apps, their state and the store; install, update, start, stop and remove apps |
| `apps:develop` | build and run development versions of apps on devices |
| `data:read`, `data:write` | read the project's data, its tables and the files apps store; create, change and delete transforms |
| `alarms:read`, `alarms:write` | read alarms; create, change and delete them |
| `logs:read` | read the logs of apps, devices and the audit log |
| `apptools:read` | list app tools and run only those marked read-only by their developer |
| `apptools:write` | list and call any app tool, including changing and unmarked tools |
| `releases:publish` | publish an app's release, for automated builds |

A sign-in or key can be restricted to selected projects or one app. The account’s own permissions apply to every tool call. A signed-in user can see a tool that requires wider consent. A key exposes only tools its scopes permit. App-tool read-only markings are the developer’s assertion. Follow the fleet skill before any changing call.

Recommend the narrowest access that fits the request:

- **Read only** (the five read scopes) for looking at a fleet: which devices
  are online, which apps run where and whether their data arrives, querying
  data, reading alarms and logs. Such a key cannot install, start, stop,
  update or remove apps, create or delete devices, change alarms or
  transforms, or call app tools. The preset includes neither `apptools:read`
  nor `apptools:write`. Add `apptools:read` explicitly only when the person
  wants developer-marked app reads; select `apptools:write` separately for
  changing calls, with the narrowest project or app restriction.
- Restrict access to the projects or the single app the person needs.
- Write scopes only when the person wants Claude to act, and
  `releases:publish` only for automated builds.
