from __future__ import annotations

import asyncio

from . import __main__ as legacy
from .publishing_v2 import install_publishing
from .remix_runtime import install_remix
from .review_runtime import install_review
from .v2_runtime import install


# Install isolated v2 modules over the stable runtime. The legacy module still owns
# scheduling, shop, analytics and existing commands until each domain is migrated
# deliberately.
studio, v2_router = install(legacy)
remix, remix_router = install_remix(legacy)
director, editorial_memory, review_router = install_review(legacy)
publishing = install_publishing(legacy, editorial_memory)


async def main():
    await legacy.main()


if __name__ == "__main__":
    asyncio.run(main())
