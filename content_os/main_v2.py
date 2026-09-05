from __future__ import annotations

import asyncio

from . import __main__ as legacy
from .v2_runtime import install


# Install isolated v2 modules over the stable runtime. The legacy module still owns
# scheduling, publishing, shop, analytics and existing commands until each domain
# is migrated deliberately.
studio, v2_router = install(legacy)


async def main():
    await legacy.main()


if __name__ == "__main__":
    asyncio.run(main())
