<!-- TODO: IronFlock shows this file to the people who install the app. Rewrite it
for what this app does; keep developer information in CLAUDE.md. -->

# App Starter

App Starter watches the machine at each of your devices: its temperature and
pressure, and whether it runs hotter than the limit you set.

## What it does

- Reads the machine connected to each device every few seconds.
- Shows all devices on one board: each machine's temperature now, its state
  (OK, too hot, no reading) and its temperature over the last 24 hours.
- Opens each device's live view inside the board, wherever you are.
- Applies the temperature limit you set on the board's Settings page to every
  device at once, also to devices that are offline at the time, as soon as they
  are back.

## Setup

1. Install the app on the devices connected to your machines.
2. Optional: set a device's sample interval, between 1 and 60 seconds (default 5),
   in the app's parameters for that device.
3. Set the maximum temperature on the board's Settings page.

## Live view and remote access

Each device serves a live view of its machine. Installing the app switches on a
remote-access tunnel for it, and the board shows it on each device's page. Only
people who are signed in to IronFlock and have access to the device can open it.
Users with the network privilege on a device can switch the tunnel off in the
device's app settings.
