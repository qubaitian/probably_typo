"""把 tui.py 放进 pty,经 WebSocket 接到浏览器里的 xterm. 每个标签页一局游戏."""

import argparse
import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import sys
import termios
import webbrowser
from pathlib import Path

from aiohttp import WSMsgType, web

ROOT = Path(__file__).parent
WEB = ROOT / "web"


def set_size(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def spawn_game() -> tuple[int, int]:
    env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", "LANG": "en_US.UTF-8"}
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(ROOT)
        os.execve(sys.executable, [sys.executable, "tui.py"], env)
    os.set_blocking(fd, False)
    return pid, fd


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB / "index.html")


async def terminal(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pid, fd = spawn_game()
    set_size(fd, int(request.query["cols"]), int(request.query["rows"]))

    loop = asyncio.get_running_loop()
    output: asyncio.Queue[bytes] = asyncio.Queue()

    def on_readable() -> None:
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        if not data:
            loop.remove_reader(fd)
        output.put_nowait(data)

    async def pump() -> None:
        while data := await output.get():
            await ws.send_bytes(data)
        await ws.close()

    loop.add_reader(fd, on_readable)
    pump_task = asyncio.create_task(pump())
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            payload = json.loads(msg.data)
            if "input" in payload:
                os.write(fd, payload["input"].encode())
            else:
                set_size(fd, payload["cols"], payload["rows"])
    finally:
        pump_task.cancel()
        loop.remove_reader(fd)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        os.close(fd)
    return ws


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", terminal)
    app.router.add_static("/vendor", WEB / "vendor")

    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_open:

        async def open_browser(_: web.Application) -> None:
            asyncio.get_running_loop().call_later(0.3, webbrowser.open, url)

        app.on_startup.append(open_browser)

    web.run_app(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
