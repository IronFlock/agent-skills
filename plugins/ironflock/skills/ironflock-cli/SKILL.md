---
name: ironflock-cli
description: Machine work with the `ironflock` command in a shell, where Claude can run commands - install the device agent on a machine and connect it to IronFlock as a new device, log in to an instance with an API key, check a machine or a device's health locally (status, doctor), delete a device, install or update the command itself, or work on another machine over SSH with --host. Use this whenever the user asks to connect, set up, install or check a machine, a Raspberry Pi, a test machine or an edge computer as an IronFlock device, mentions the ironflock command, a .flock file, ironflock login, agent install, doctor or --host, or an ironflock command fails.
metadata:
  mcp-tools: none
---

# The `ironflock` command

`ironflock` is IronFlock's command for work on a machine: installing the
device agent, connecting the machine as a device, checking whether it can run
the agent and whether the agent is connected. This skill is about when to use
it and how to use it with judgement. It does not list flags: the command
explains itself, and its help is always right for the version that is
installed.

**This is the one skill that needs a shell on the person's own machine, or on
the machine that is to be set up** (Claude Code on that computer, or a shell
that reaches the machine over SSH). A sandbox shell in the Claude app or in
Cowork is not that machine: a command run there changes the sandbox, not the
person's machine. Without such a shell, tell the person the commands to run
themselves; do not pretend to run them. No other skill depends on this one.

## Rules

- **The API key never goes on a command line, into the chat, or into a file you
  write.** `ironflock login` takes it from a file the person keeps (`--key-file`)
  or from a pipe. Never ask the person to paste a key into the chat. If they
  paste one anyway, do not repeat it, do not use it, do not write it anywhere;
  tell them it is now part of this conversation, that they should delete that
  key in Studio, create a new one and log in with it from a file.
- **A `.flock` file is a credential**: it holds the device's secrets, and the
  platform shows them only once, when the device is created. Do not print it,
  do not open it to look inside, do not copy it into the chat, a repository, a
  commit or a log, and do not leave copies around (no `cat`, `head`, `less`,
  `jq` or `cp` of it). Never write it where others can read it. The command
  does not print it either. Prefer the flow that never writes the file at all:
  `agent install --project --name`, where it stays in memory (see
  [Connect a new device](#connect-a-new-device)), or Studio.
- **Ask before you change a machine or the platform.** Get a clear yes, in this
  conversation, to the exact thing, before you:
  - install the agent on a machine, or remove, update or reconfigure it;
  - delete a device (it cannot be brought back, and its stored data stays tied
    to a device that no longer exists);
  - run a command that changes another machine with `--host`: say which
    machine, as which user, and what runs there.
  Reading commands (`version`, `whoami`, `status`, `doctor`, `device list`,
  and reads of logs), on this machine or, with `--host`, on a machine the
  person has named, need no question. `--yes` skips the command's own question, so give it only
  after the person has said yes to what that question would have asked, never
  to get past it.
- **Read the command's own help instead of guessing flags**:
  `ironflock --help`, `ironflock <group> --help`, `ironflock <group> <verb> --help`.
  Do this before the first use of a command you are not sure about. Do not
  copy the help into your answer; say what the person needs and name the help
  for the rest.
- Do not invent flags, and do not run `sudo` or install software the person did
  not ask for.

## 1. Is the command the right tool?

| The person wants | Use |
|---|---|
| install the agent on a machine, connect a machine as a device, check a machine, set up a test machine | **the command**, on that machine or over `--host` |
| see, start, stop or update apps on devices; read data, logs, alarms; look at a fleet from anywhere | the IronFlock MCP tools (see `ironflock-connect`), not this skill |
| create or delete a device without a machine to put it on | the MCP tools, or `ironflock device delete` (with its question) in a shell with a login; `device create` only as described under [Connect a new device](#connect-a-new-device) |

The command works on the machine it runs on (or the one named with `--host`);
the MCP tools work on the fleet through the platform. Machine work is the
command's. If the person has no shell on the machine and no SSH access to it,
the command cannot help; say so and say what they need.

## 2. Is it installed, and current?

1. Run `ironflock version`. If the command is not found, it is not installed.
2. Run `ironflock version --check` to see whether a newer release is out.
   Updating changes the machine: ask first, then `ironflock self-update` (it
   needs root, and asks itself).
3. To install it: the person runs the install line of the
   [installation page](https://ironflock.com/docs/app-development/cli/installation/)
   (Linux and macOS, with `sudo`; Windows has a PowerShell line). Show them the
   line from that page rather than from memory, and do not run a script that
   you piped from the internet without their yes. The script checks its
   download's signature.

Several things in this skill need a release of the command that has `login`
and `device`. If `ironflock login --help` does not exist, the command is too
old: update it first.

## 3. Log in

Only the commands that ask the platform need a login: `device ...` and the
`--project` / `--name` install. Check first with `ironflock whoami`; it names the
account, the key's scopes and its restrictions, and does not change anything.
A login is only needed if `whoami` says there is none or the key is rejected.

To log in the person creates an API key in Studio (see `ironflock-connect` for
where) and saves it to a file only they can read, such as one in their home
folder with mode 600, outside any repository. Then run
`ironflock login --key-file <that file>` (add `--instance` for an appliance, or
the person's own instance, otherwise the cloud is used). A key piped in on
standard input works as well. The command never asks for the key at a
terminal, and refuses a key given as an argument.

Afterwards run `ironflock whoami` and tell the person which account and scopes
it shows. Creating a device needs the scope to write devices; a 403 means the
key lacks it. The person can end a login with `ironflock logout`, and should
delete a key in Studio when it is no longer needed.

A command run with `sudo` looks for root's login, not the person's. `agent
install` needs root. Either the person logs in as root, or passes the key's
environment variable through `sudo` (the install section of the command's help
says how), or you run it from the person's own machine with `--host`. Do not
put the key on the `sudo` line.

On an appliance, login works only when its release runs the platform's API
service; if `login` answers with a 404, say that this instance does not offer
it yet and do not promise a date.

## Connect a new device

The usual job: "connect this test machine as a new device in project X". The
command creates the device and installs the agent in one step, and the
device's `.flock` is held in memory and in a private temporary folder that goes
away, so it never ends up in your hands or in a file you could leak.

1. Find out the **project** (its name or its number) and the **name** the new
   device should get. Ask if the person has not said. Names are letters,
   digits, dots, underscores and hyphens.
2. Check the machine: `ironflock doctor` changes nothing and says whether the
   machine can run the agent and reach the hosts it needs. Fix what it reports
   as failed before you install (read its hints).
3. Check the login (`whoami`), as above. Check that the project is one the key
   can work in (`ironflock device list --project <project>` reads the project's
   devices and also shows whether the name is already taken).
4. **Say what is about to happen and ask**: a device with that name is created
   in that project of that instance, and the agent is installed on this machine
   (or on the machine named with `--host`), which installs software, starts
   services and needs root. Wait for a yes.
5. Read `ironflock agent install --help`, then run it with `--project` and
   `--name` in place of `-c`. Use `--yes` only after the yes of step 4.
6. Check the result: `ironflock status`, and after a minute
   `ironflock device list --project <project>` to see whether the device is
   online.

**If the person needs the `.flock` for another machine** (one you cannot
reach, or an image to flash): `ironflock device create --project <project>
--name <name> -o <path>`, where `-o` is required and the path is one the
person names, outside any repository, in a folder only they can read. Never
print the file, never use `-o -` where the output would show here, and never
open it. Tell them to move it to the device and delete every other copy, and
that the platform will not show it again.

**When the device already exists**: the platform gives a device's `.flock` only
once, in the answer that creates it. If the person has the `.flock` of that
device, install with `-c <file>.flock` instead of `--project` and `--name`.
Never open the file. If the person does not have it, the name is taken and the
command says so (a 409): they choose another name, or delete the old device,
which needs its own confirmation (see below), and then run the flow again.

**If it fails after the device was created**, the error says so and names the
`device delete` to run, because that device's credentials were kept nowhere.
Read the error to the person, ask before deleting, delete, fix the cause, and
run the flow again. The same name is refused while the device exists.

## Delete a device

Deleting is permanent. Find the device with `ironflock device list --project
<project>` (it shows the device's key), say which device in which project of
which instance, and ask. Only after a yes run `ironflock device delete`; the
command asks again itself and asks nothing without a terminal, where it ends
with exit code 4 unless `--yes` is given. A delete of the device a machine
still runs leaves that machine without its device: say so, and ask whether the
agent on it should go too (`ironflock agent remove`, again with its own yes).

## Another machine: `--host`

`ironflock --host [user@]machine <command>` runs the command on that machine
over SSH, using the SSH settings of this computer. Before you use it:

- Reads (`status`, `doctor`, `version`, reads of logs) over `--host` run
  without another yes once the person has named the machine. Never pick a
  machine yourself.
- Anything that changes the other machine (install, remove, update,
  configure, restart, stop) needs a yes that names the machine, the user and
  what runs there, as in the rules.
- `login`, `logout`, `whoami` and the `device` commands do not take `--host`:
  they act on this computer. The `--project` / `--name` install does the
  platform's part here and sends only the `.flock` to the machine; the key
  never goes there.
- The machine needs an SSH server, a POSIX login shell and Linux; the help
  and the
  [remote machines page](https://ironflock.com/docs/app-development/cli/remote-machines/)
  describe the rest. Exit code 255 means the SSH connection itself failed.

## When it fails

1. Read the **exit code** and the **`Error:` lines** on stderr. The code says
   the kind of failure: 1 the command started and could not finish, 2 the
   command line is wrong (nothing was touched; read `--help`), 3 the machine is
   not in the state the command needs (not root, an agent installed already,
   no login; nothing was touched), 4 the question was answered no or could not
   be asked (nothing was changed), 130 interrupted, 255 the SSH connection of
   `--host` failed.
2. Tell the person what the error says, in their words. Do not paste output
   that could hold a secret; the command prints none, but a file or a log you
   read may.
3. For a machine that will not install, or a device that does not come online,
   run `ironflock doctor` (and `status`), read its findings and hints, and act
   on the failed ones. `doctor` exits 1 when a check failed; that is a result,
   not a fault of the command.
4. Do not retry a failing change in a loop, and do not add `--yes` or `sudo` to
   push past a refusal (a declined question is the person's no). If a device
   was created and the install failed, follow the error's delete advice as
   described above.
5. The person may find more in the
   [command's pages](https://ironflock.com/docs/app-development/cli/) (the
   agent, status and doctor, flags, output and exit codes).

## Summary of what you tell the person

After the work, in a few sentences: what you ran, whether it worked (exit code
and what `status` or `device list` shows), what is left to do, and that the
`.flock` (if one exists) is a credential to keep private. Never include a key,
or any part of one.
