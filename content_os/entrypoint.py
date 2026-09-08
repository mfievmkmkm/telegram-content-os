from __future__ import annotations

import asyncio
import os


def runtime_name() -> str:
    value = (os.getenv("CONTENT_OS_RUNTIME") or "legacy").strip().lower()
    return "v2" if value in {"v2", "2", "next", "content-os-v2"} else "legacy"


async def main():
    if runtime_name() == "v2":
        from .main_v2 import main as run
    else:
        from .__main__ import main as run
    await run()


if __name__ == "__main__":
    asyncio.run(main())
