from __future__ import annotations

import asyncio
import os


def runtime_name() -> str:
    # V2 is the production product. Legacy remains an explicit rollback switch,
    # never an accidental default that silently restores the old navigation.
    value = (os.getenv("CONTENT_OS_RUNTIME") or "v2").strip().lower()
    return "legacy" if value in {"legacy", "v1", "1", "rollback"} else "v2"


async def main():
    if runtime_name() == "v2":
        from .main_v2 import main as run
    else:
        from .__main__ import main as run
    await run()


if __name__ == "__main__":
    asyncio.run(main())
