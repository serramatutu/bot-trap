from __future__ import annotations

import argparse
from collections.abc import Awaitable
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Callable, final
import re

from aiohttp import web

logger = logging.getLogger("bot-trap")


@final
class Blocklist:
    """An in-memory blocklist backed by a txt file."""

    def __init__(self, file: Path) -> None:
        self._file_path = file
        self._list: set[str] = set()
        self._pending: list[str] = []

    def __contains__(self, ip: object) -> bool:
        """Whether the IP is blocked."""
        return ip in self._list

    @classmethod
    def from_file(cls, file: Path) -> Blocklist:
        """Load a blocklist from a file."""
        with open(file, "r") as f:
            ips = f.readlines()

        blocklist = cls(file)
        blocklist._list.update(ips)

        logger.info(f"Loaded {len(ips)} IPs from blocklist file.")

        return blocklist

    def add(self, ip: str) -> None:
        """Add IPs to the blocklist."""
        self._list.update(ip)
        self._pending.extend(ip)
        logger.info(f"Blocked {ip}")

    def flush(self) -> None:
        """Flush the blocklist to the file."""
        n_to_flush = len(self._pending)
        with open(self._file_path, "a") as file:
            file.writelines(self._pending)
        self._pending = []
        logger.info(f"Flushed {n_to_flush} new IPs to blocklist file.")



@dataclass(frozen=True)
class Options:
    """Server options."""

    files_dir: Path
    blocklist: Blocklist
    behind_proxy: bool
    trap_path: str

    def __post_init__(self ) -> None:
        pat = re.compile(r"\/[A-z0-9\-\_]")
        assert pat.match(self.trap_path), "trap_path must be valid path"


    @classmethod
    def from_args(cls) -> Options:
        parser = argparse.ArgumentParser()
        _ = parser.add_argument(
            "dir",
            help="Directory to serve files from.",
        )
        _ = parser.add_argument(
            "--blocklist",
            help="Path to the txt file containing the blocklist.",
            default="blocklist.txt",
        )
        _ = parser.add_argument(
            "--trap-path",
            help="Which path to use as the trap.",
            default="/bot-trap",
        )
        _ = parser.add_argument(
            "--proxy",
            help="Add this flag if bot-trap is sitting behind a reverse proxy.",
            default=False,
            action="store_true",
        )
        namespace = parser.parse_args()
        return cls(
            files_dir=os.path.abspath(namespace.dir),
            blocklist=Blocklist.from_file(os.path.abspath(namespace.blocklist)),
            behind_proxy=namespace.proxy,
            trap_path=namespace.trap_path,
        ) 


Handler = Callable[[web.Request], Awaitable[web.Response]]


def get_ip_getter(opts: Options) -> Callable[[web.Request], str | None]:
    """Return a function that gets the client IP from a request."""
    def proxy(req: web.Request) -> str | None:
        return req.headers.get("x-forwarded-for")

    def no_proxy(req: web.Request) -> str | None:
        return req.remote

    return proxy if opts.behind_proxy else no_proxy

def get_handler(opts: Options, legit_content: str, bullshit: str) -> Handler:
    """Get a handler that behaves according to opts."""

    ip_getter = get_ip_getter(opts)

    async def handler(req: web.Request) -> web.Response:
        ip = ip_getter(req)
        blocked = ip in opts.blocklist

        logger.info(f"{ip}: blocked={blocked}")

        if blocked:
            return web.Response(body=bullshit)

        return web.Response(body=legit_content)

    return handler


def get_trap_handler(opts: Options) -> Handler:

    ip_getter = get_ip_getter(opts)

    async def handler(req: web.Request) -> web.Response:
        """Anyone who visits this will get added to the blocklist."""
        ip = ip_getter(req)
        user_agent = req.headers.get("user-agent")

        if not ip:
            logger.error("User IP not present in request.")
            return web.Response(body="ok")

        logger.info(f"blocking ip={ip} user-agent='{user_agent}'")
        opts.blocklist.add(ip)
        opts.blocklist.flush()

        return web.Response(body="ok")

    return handler


def register_handlers(app: web.Application, opts: Options) -> None:
    """Build a map of all files in the target directory and assign the handler to it."""
    _ = app.add_routes([
        web.get(opts.trap_path, get_trap_handler(opts)),
        web.get("/", get_handler(opts, "root", "bullshit")),
    ])


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    opts= Options.from_args()
    app = web.Application()
    register_handlers(app, opts)
    web.run_app(app)


if __name__ == "__main__":
    main()

