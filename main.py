from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Callable, final
import re

from aiohttp import web
from aiohttp.typedefs import Middleware, Handler
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro import field_options

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



@dataclass
class Options(DataClassJSONMixin):
    """Server options."""

    # Path to the folder with public contents to serve
    public: Path

    # Path to file to be returned when request is 404
    not_found: Path

    # Port to listen on
    host: str = "0.0.0.0"

    # Port to listen on
    port: int = 8080

    # Path to the bullshit file
    bullshit: Path = Path("bullshit.txt")

    # Path to the blocklist file
    blocklist_path: Path = field(metadata=field_options(alias="blocklist"), default=Path("blocklist.txt"))
    blocklist: Blocklist = field(init=False, metadata=field_options("omit"))

    # Whethere bot-trap is sitting behind a reverse proxy
    proxy: bool = False

    # The trap path
    trap: str = "/bot-trap"

    # The directory anchor to use for all relative paths in this Options object
    # Defaults to the parent directory of the config file.
    anchor: Path | None = None

    def __post_init__(self) -> None:
        pat = re.compile(r"\/[A-z0-9\-\_]")
        assert pat.match(self.trap), "trap must be valid HTTP path"

        anchor = self.anchor or os.getcwd()

        self.public = Path(os.path.join(anchor, self.public))
        self.not_found = Path(os.path.join(anchor, self.not_found))
        self.bullshit = Path(os.path.join(anchor, self.bullshit))
        self.blocklist_path = Path(os.path.join(anchor, self.blocklist_path))

        self.blocklist = Blocklist.from_file(self.blocklist_path)

    @classmethod
    def from_file(cls, file: Path) -> Options:
        abs_path = os.path.realpath(file)

        with open(abs_path, "r") as f:
            raw_config = json.loads(f.read())

        if "anchor" not in raw_config:
            raw_config["anchor"] = os.path.dirname(abs_path)

        return cls.from_dict(raw_config)



def get_ip_getter(opts: Options) -> Callable[[web.Request], str | None]:
    """Return a function that gets the client IP from a request."""
    def proxy(req: web.Request) -> str | None:
        return req.headers.get("x-forwarded-for")

    def no_proxy(req: web.Request) -> str | None:
        return req.remote

    return proxy if opts.proxy else no_proxy

def get_blocklist_middleware(opts: Options, bullshit: str) -> Middleware:
    """Get a middleware that blocks people that are in the blocklist."""

    ip_getter = get_ip_getter(opts)

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        ip = ip_getter(request)
        blocked = ip in opts.blocklist

        logger.info(f"{ip}: blocked={blocked}")
        if blocked:
            return web.Response(body=bullshit)

        return await handler(request)

    return middleware


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

def get_robots_txt_handler(opts: Options) -> Handler:
    robots_txt_path = os.path.join(opts.public, "robots.txt")

    if os.path.isfile(robots_txt_path):
        with open(robots_txt_path, "r") as f:
            contents = f.read()
    else:
        contents = ""

    inject = f"User-Agent: *\nDisallow: {opts.trap}\n\n"
    contents = inject + contents

    async def handler(_: web.Request) -> web.Response:
        """Return the modified robots.txt."""
        return web.Response(body=contents)

    return handler


def main() -> None:
    logging.basicConfig(level=logging.INFO)


    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "config_file",
        help="bot-trap.json config file.",
    )
    namespace = parser.parse_args()
    opts= Options.from_file(Path(namespace.config_file))

    with open(opts.bullshit, "r") as f:
        bullshit = f.read()

    app = web.Application(middlewares=[
        get_blocklist_middleware(opts, bullshit)
    ])
    _ = app.add_routes([
        web.static("/", opts.public, show_index=True),
        web.get(opts.trap, get_trap_handler(opts)),
        web.get("/robots.txt", get_robots_txt_handler(opts)),
    ])

    web.run_app(app, host=opts.host, port=opts.port)


if __name__ == "__main__":
    main()

