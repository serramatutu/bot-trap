from __future__ import annotations

import asyncio
import argparse
from dataclasses import dataclass
from enum import StrEnum



class BlockBehavior(StrEnum):
    """How to behave when a request is blocked."""
    HARD_BLOCK = "hard-block"
    SOFT_BLOCK = "soft-block"


@dataclass(frozen=True)
class Options:
    """Server options."""

    trap_path: str
    block_behavior: BlockBehavior

    @classmethod
    def from_args(cls) -> Options:
        parser = argparse.ArgumentParser()
        _ = parser.add_argument(
            "--trap-path",
            default="bot-trap",
        )
        _ = parser.add_argument(
            "--block-behavior",
            default="hard-block",
        )
        namespace = parser.parse_args()
        return cls(
            trap_path=namespace.trap_path,
            block_behavior=BlockBehavior(namespace.block_behavior),
        ) 



async def main() -> None:
    options = Options.from_args()
    print(options)


if __name__ == "__main__":
    asyncio.run(main())
