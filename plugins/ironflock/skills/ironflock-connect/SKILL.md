---
name: ironflock-connect
description: Connect Claude to IronFlock, in the cloud or on an appliance, through IronFlock's MCP endpoint and an API key, and check that the connection works. Use this whenever the user wants to connect Claude (Claude Code, the Claude app, claude.ai or Cowork) to IronFlock, set up or change the IronFlock API key or address, asks where the key goes, when the IronFlock tools are missing or fail to connect (401, unauthorized, not reachable), or asks what an IronFlock API key lets Claude do.
metadata:
  mcp-tools: list_projects list_devices
  min-api-version: 2.0.0
---

# Connect Claude to IronFlock

IronFlock offers its projects, devices, apps and data to Claude as an MCP
server. Claude reaches it at the API address of the IronFlock instance and
proves who it acts for with an API key, sent as `Authorization: Bearer <key>`
on every request. There is no sign-in through a browser (OAuth); the key is the
only way in.

You guide the person through the steps; they enter the key themselves, in
Claude's own settings. Then you check the connection with a first read.

This skill needs version 2.0.0 or later of the IronFlock API service, the
first with the MCP endpoint. That is the version of the API service itself,
not the IronFlock release a person sees in Studio.

## Rules

- **Never ask for the key in the chat, and never put it anywhere yourself.**
  The key goes into Claude's settings, typed by the person: the plugin's
  configuration in Claude Code, or a connector's request header in the Claude
  app. Not into a message, a file, a command line, an environment file or a
  repository.
- **If the person pastes a key into the chat anyway**, do not repeat it, do not
  use it, and do not write it anywhere. Tell them that it is now part of this
  conversation, that they should delete that key in Studio, create a new one
  and enter the new one in the settings as described below.
- The check after connecting only reads. Do not change anything on the
  instance to test the connection.
- Describe what the person sees and does. Do not guess at screens this skill
  does not describe; if a step looks different for them, ask what they see.

## 1. Find out where the person is

If the IronFlock tools are already available to you, go straight to
[Check the connection](#4-check-the-connection).

Otherwise find out two things, and ask when you cannot tell:

1. **Which Claude.** The steps differ:
   - **Claude Code**: in a terminal, in an IDE extension, or in the Code tab
     of the Claude desktop app. The `ironflock` plugin connects by itself once
     the person has entered the key.
   - **The Claude app**: chat on claude.ai, in the desktop app or on a phone,
     and **Cowork**. The person adds IronFlock as a custom connector.
2. **Which IronFlock.**
   - **The cloud**, ironflock.com: the API address is
     `https://api.ironflock.com`, the MCP endpoint
     `https://api.ironflock.com/mcp`. No slash at the end of the address:
     `https://api.ironflock.com/` would become `…//mcp`.
   - **An appliance**, IronFlock installed on the company's own server: the
     API address is `https://api.` followed by the appliance's domain, the MCP
     endpoint that address with `/mcp` at the end. The appliance's
     administrator knows the domain. An appliance offers this only once it
     runs the IronFlock API service, which comes with a later appliance
     release. Until then its Studio has no API keys, and its API address does
     not answer at `/mcp`. Say so plainly; do not promise a date.

## 2. Create an API key in Studio

The person creates the key in IronFlock Studio (studio.ironflock.com for the
cloud):

1. Open the account settings (**Account Settings**) from the account in the
   top bar.
2. Choose **Developer**. The page has the section **API keys**.
3. Choose **Create API key**, give it a name that says where it will be used
   (for example "Claude Code on my laptop"), and create it.
4. Choose **Copy API key**.

The key stays visible in Studio's **API keys** table under
**Account Settings > Developer**, so anyone signed in to that Studio account
can read it: advise keeping the Studio session private. A key is valid for
one year; after that Studio marks it **Expired**, and a new one is needed.

Advise one key per place it is used, so that one can be deleted without
breaking the others, and deleting a key in Studio when it is no longer used.

Keys created today have every scope and no restriction: Claude, with such a
key, may do in IronFlock whatever the key's owner may do. See
[What a key lets Claude do](#what-a-key-lets-claude-do).

## 3. Connect

### Claude Code (terminal, IDE extensions, desktop Code tab)

The `ironflock` plugin declares the IronFlock MCP server. It has two settings,
which Claude Code asks for in its plugin dialog:

| Setting | Value |
|---|---|
| IronFlock API address | `https://api.ironflock.com` (the default) for the cloud; `https://api.<the appliance's domain>` for an appliance. Without `/mcp` and without a slash at the end; the plugin adds `/mcp`. |
| IronFlock API key | the key from Studio. The field is masked. Claude Code keeps it in the system's secure credential store (on a Mac, the Keychain), not in a settings file. |

Steps for the person:

1. If the plugin is not installed yet, in a Claude Code session:
   `/plugin marketplace add IronFlock/agent-skills`, then
   `/plugin install ironflock@ironflock`. The dialog for the two settings
   opens with the install.
2. To enter or change the settings later: `/plugin configure ironflock@ironflock`.
3. Restart Claude Code, so that it connects with the new settings.
4. `/mcp` then lists the server `plugin:ironflock:ironflock` as connected.

Until the key is set, Claude Code does not start the server at all: it is
missing from `/mcp`, and Claude Code says that a required plugin option is
not set yet. An install from a shell (`claude plugin install`) does not open
the dialog, so it ends in that state; `/plugin configure ironflock@ironflock`
in a session completes it. Avoid passing the key on a command line, where it
stays in the shell's history.

To check the connection, the person looks at `/mcp`, which shows the
server's status. Do not run commands that print a server's configuration
(its headers) yourself: the key would end up in this conversation.

The desktop app's Code tab and the IDE extensions run Claude Code, with the
same plugins and settings as the terminal on that computer.

### The Claude app: chat (web, desktop, phone) and Cowork

The plugin's own connection works only in Claude Code: the chat and Cowork do
not ask for the plugin's settings and leave out a server that needs them. So
the person adds IronFlock as a custom connector, once, and it serves the chat
and Cowork.

This needs request headers on custom connectors, a beta that is available to
a limited set of organizations. If the dialog below has no **Request headers**
section, the person's organization does not have it yet. Then IronFlock cannot
be connected in the Claude app for now, because it offers no sign-in that
would work without a header; Claude Code works.

On a Free, Pro, Max or Ultra plan:

1. Open **Customize > Connectors**, choose **Add**, then
   **Add custom connector**.
2. Name: `IronFlock`. Server URL: the MCP endpoint, for example
   `https://api.ironflock.com/mcp`. Choose **Continue**.
3. Authentication: **No sign-in**.
4. Under **Request headers**, choose the header name `authorization` and
   enter the value `Bearer `, followed by the key: the word Bearer, one space,
   then the key. Claude sends the value exactly as entered, so without
   `Bearer ` IronFlock refuses it. Mark the header as required.
5. Choose **Add**.

On a Team or Enterprise plan an Owner (on Enterprise also a member whose
role includes managing the organization's libraries) adds the connector for
the organization, under **Organization settings > Connectors**, **Add**, then
**Custom** (type **Web** if asked), with the same name, URL, authentication
and request header; the request headers may be under **Advanced**. Members
then find IronFlock under **Customize > Connectors** with the label
**Custom** and choose **Connect**. Everyone who uses this connector acts with
the one key the Owner entered, so with that key's owner's rights in
IronFlock. Point this out, and suggest a key of an account that may see only
what all members may see.

Also good to know:

- A connector's request headers cannot be edited. To change the key, the
  connector is removed and added again.
- In a chat, connectors are switched on and off under **+** > **Connectors**.
- A connector added on the web or in the desktop app is also available in the
  phone apps.
- The connector connects from Anthropic's servers, not from the person's
  computer. The IronFlock address must therefore be reachable from the
  internet. For the cloud it is. An appliance that only the company network
  reaches usually cannot be connected in the Claude app, while Claude Code on
  a computer in that network can. For servers inside a private network,
  Anthropic offers MCP tunnels to Enterprise organizations, as a research
  preview on request (see Anthropic's page on
  [adding a connector that isn't in the directory](https://claude.com/docs/connectors/custom/add-unlisted));
  whether that fits is for the organization's administrators to find out.
- The skills of the `ironflock` plugin come from the plugin, which is added
  under **Customize > Plugins**; the connector is added separately as above.

## 4. Check the connection

1. Call `list_projects`. Tell the person how many projects the key can work
   in and name them. A key restricted to one app is not offered this tool; ask
   which project the app is in instead.
2. Choose a project (ask if there are several and the person has not named
   one) and call `list_devices` for it. Tell the person how many devices it
   has, how many are online, and name a few.
3. Where your client shows the server's details: the server names the
   version of the API service when Claude connects (its server info, for
   example 2.0.1; not the IronFlock release), and an appliance calls itself
   "IronFlock appliance". An API service older than 2.0.0 has no `/mcp` at
   all, so the connection fails with HTTP 404 before any version shows. A
   later skill may need a newer API service than this one; it says so.

If both reads work, the connection is done. Say so in one sentence, with the
project and device counts.

## 5. When it does not work

| What happens | Likely cause | What the person does |
|---|---|---|
| HTTP 401 "The API key is not valid." or "An API key is required. …"; Claude Code reports that the server rejected the Authorization header in its config | The key was deleted, mistyped or cut off, or has expired (Studio marks it **Expired**); in a connector, `Bearer ` is missing; or the key belongs to another IronFlock (a cloud key on an appliance, or the reverse) | Create a new key in Studio of the instance they connect to and enter it again (Claude Code: `/plugin configure ironflock@ironflock` and a restart; connector: remove and add again). |
| HTTP 429 "This API key has made too many requests. Wait N seconds before the next one." or "This API key has too many requests open at once. …" | More requests with this key than IronFlock allows per minute, or too many at the same time | Wait as long as the answer says (also in its `Retry-After`), then go on with fewer calls at once. |
| HTTP 503 "The platform is not available at the moment. Try again shortly." or "The service is shutting down. Try again shortly." | IronFlock is restarting or briefly unavailable | Try again in a minute; if it lasts, tell the person to contact IronFlock support or, for an appliance, its administrator. |
| HTTP 504 "The platform did not answer in time. Try again shortly." | IronFlock is busy | The same. |
| HTTP 403 | Something between Claude and IronFlock refuses the request: a company proxy or firewall | Ask the network's administrator to allow the API address. |
| Not reachable, timeout, connection refused, name not found | Wrong address; an appliance that cannot be reached from where Claude connects (see above); no network | Check the address (`https://api.…`, without `/mcp` and without a slash at the end in the Claude Code setting); for an appliance, check from a browser on the same computer that its Studio opens. |
| HTTP 404 at `/mcp` | `/mcp` twice or `//mcp` in the address, or an instance without the MCP endpoint (an appliance that does not run the IronFlock API service yet, or an API service older than 2.0.0) | Fix the address; otherwise tell the person that this instance does not offer the connection yet. |
| In Claude Code, the server is missing from `/mcp` | The key is not set yet, or the plugin is not enabled | `/plugin configure ironflock@ironflock`, then restart. |
| IronFlock appears twice | Claude Code treats the plugin's server and a connector of the Claude app with the same address as one server, so two show only when the addresses differ (another host, or a slash at the end) | Use the same address in both, or remove one. |
| Connected, but a tool you expected is missing | The key's scopes or its restriction leave it out, or the API service is older | Explain which; a key with the needed scope, or an update of the instance, brings it. |
| A tool answers with an error sentence | IronFlock explains in that sentence what went wrong, for example that a project does not exist or that the platform did not answer in time | Act on the sentence. |

## What a key lets Claude do

An IronFlock API key carries scopes, each of which allows one area to be read
or changed:

| Scope | Allows |
|---|---|
| `devices:read`, `devices:write` | read the devices and projects; create and delete devices |
| `apps:read`, `apps:write` | read the installed apps, their state and the store; install, update, start, stop and remove apps |
| `data:read`, `data:write` | read the project's data, its tables and the files apps store; create, change and delete transforms |
| `alarms:read`, `alarms:write` | read alarms; create, change and delete them |
| `logs:read` | read the logs of apps, devices and the audit log |
| `apptools:call` | list and call the tools that apps bring, which run on devices and can change things there |
| `releases:publish` | publish an app's release, for automated builds |

A key may also be restricted to some projects or to one app. Whatever the
key allows, Claude never does more than the key's owner may do in IronFlock.
The server offers Claude only the tools the key allows, and marks the tools
that change or delete something, so that Claude asks before using them.

Keys created today have every scope and no restriction. Once Studio offers
scopes and restrictions, recommend the smallest key that does the job:

- **Read only** (the five read scopes) for looking at a fleet: which devices
  are online, which apps run where and whether their data arrives, querying
  data, reading alarms and logs. Such a key cannot install, start, stop,
  update or remove apps, create or delete devices, change alarms or
  transforms, or call app tools.
- Restricted to the projects the person works on, and for a connector that a
  whole organization shares, to what all its members may see.
- Write scopes only when the person wants Claude to act, and
  `releases:publish` only for automated builds.
