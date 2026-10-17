"""App Starter: the edge program of an IronFlock app.

It runs in a container on every device the app is installed on and talks to the
rest of the platform only through the IronFlock SDK, by way of the app's tables
(.ironflock/data-template.yml):

    devices       this device writes its own row: its state and its live view's URL
    measurements  this device writes one row per reading of the machine
    settings      the board's Settings form writes it; every device applies the
                  newest row and each one saved after it

The board (.ironflock/board-template.yml) reads and writes the same tables, so
neither side calls the other, and neither needs the other to be online.

The live view on port 8080 is a web page this device serves itself. The
port-template offers it as a remote-access tunnel, and the board embeds it on
the device's page through the URL this program writes into the devices table.
"""

import asyncio
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from ironflock import IronFlock

UI_PORT = 8080  # the port in .ironflock/port-template.yml
SAMPLE_INTERVAL = float(os.environ.get("SAMPLE_INTERVAL", "5"))  # env-template.yml, same default
DEVICE_NAME = os.environ.get("DEVICE_NAME", "this device")
PAGE = Path(__file__).parent / "web" / "index.html"

flock: IronFlock  # created in __main__ below
settings = {"max_temperature": 80.0}  # in force until someone saves the Settings form
settings_tsp = 0  # tsp of the settings row in force, in epoch ms as the tables return it
latest: dict = {}  # the newest reading, sent to a live view as soon as it opens
viewers: set[web.WebSocketResponse] = set()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_machine() -> dict:
    """Read the machine. This one is simulated: replace it with the real driver
    (Modbus, OPC UA, serial, ...), and let it raise when the machine cannot be read."""
    t = time.time()
    return {
        "temperature": round(70 + 15 * math.sin(t / 120) + random.uniform(-1, 1), 1),
        "pressure": round(3 + 0.5 * math.sin(t / 45) + random.uniform(-0.05, 0.05), 2),
    }


# --- settings: written on the board, applied here ---------------------------


def apply_settings(row: dict) -> None:
    """Apply a settings row unless a newer one is in force already.

    Rows come from the first read and from the subscription, and a row saved
    just as the program starts can come from both, so the newest row wins."""
    global settings_tsp
    if row.get("tsp", 0) <= settings_tsp or row.get("max_temperature") is None:
        return
    settings["max_temperature"] = float(row["max_temperature"])
    settings_tsp = row["tsp"]
    print(f"Settings applied: maximum temperature {settings['max_temperature']} °C")


async def load_settings() -> None:
    """Read the settings in force: the newest row of the settings table."""
    rows = await flock.getHistory("settings", {"limit": 1, "filterAnd": [{"latest": True}]})
    for row in rows or []:
        apply_settings(row)


def on_settings(*args, **kwargs) -> None:
    """A settings row the board saved. Rows saved while this device was offline
    arrive too: the SDK delivers them as soon as the connection is back."""
    apply_settings(args[0])


# --- live view: a web page this device serves on UI_PORT -------------------


async def page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(PAGE)


async def updates(request: web.Request) -> web.WebSocketResponse:
    """Push every reading to an open live view. The page only listens."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    viewers.add(ws)
    try:
        if latest:
            await ws.send_json(latest)
        async for _ in ws:
            pass
    finally:
        viewers.discard(ws)
    return ws


async def serve_live_view() -> None:
    app = web.Application()
    app.router.add_get("/", page)
    app.router.add_get("/ws", updates)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", UI_PORT).start()


async def show(reading: dict | None, state: str) -> None:
    latest.update(reading or {"temperature": None, "pressure": None})
    latest.update(device=DEVICE_NAME, state=state, tsp=now(), **settings)
    await asyncio.gather(*(ws.send_json(latest) for ws in viewers), return_exceptions=True)


async def announce() -> None:
    """Write this device's row with the URL the board embeds as its live view.

    Only production installs get remote-access tunnels. A development run writes no
    URL; open its live view on the device's network, at the address printed here."""
    production = os.environ.get("ENV", "").upper() == "PROD"
    url = flock.getRemoteAccessUrlForPort(UI_PORT) if production else None
    await flock.append_to_table("devices", {"tsp": now(), "ui_url": url})
    lan = f"http://{os.environ.get('DEVICE_LAN_IP')}:{os.environ.get(f'DEVICE_PORT_FOR_{UI_PORT}')}"
    print(f"Live view: {url or 'no tunnel in development'}, on the device's network: {lan}")


# --- main -------------------------------------------------------------------


async def main() -> None:
    await serve_live_view()
    await flock.subscribe_to_table("settings", on_settings)  # before the read, so no row falls between
    await load_settings()
    await announce()

    state = None  # what this device's row in the devices table says
    while True:
        try:
            reading, problem = read_machine(), None
        except Exception as error:
            reading, problem = None, error
        if problem:
            new_state = "NO_READING"
        else:
            new_state = "TOO_HOT" if reading["temperature"] > settings["max_temperature"] else "OK"
        await show(reading, new_state)
        # Readings are published: a publish waits for the connection, up to the SDK's
        # reconnect window, but not for the data backend, so a reading published while
        # the data backend restarts is lost, which is fine at this rate. State changes
        # are appended: an append waits for the data backend too, so a short outage
        # loses none. A longer outage raises, and the next round tries again.
        try:
            if reading:
                await flock.publish_to_table("measurements", {"tsp": now(), **reading})
            if new_state != state:
                if new_state == "NO_READING":
                    await flock.report_error(problem, append=True, user_message=f"{DEVICE_NAME} cannot read the machine")
                await flock.append_to_table("devices", {"tsp": now(), "state": new_state})
                state = new_state
        except RuntimeError as error:
            print(f"Not recorded: {error}")
        await asyncio.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    # The program is PID 1 in its container, which ignores SIGTERM unless it handles
    # it: without this, stopping the app waits until Docker kills it.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    flock = IronFlock(mainFunc=main)
    flock.run()
