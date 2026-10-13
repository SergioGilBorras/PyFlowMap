async def load(manager, key):
    try:
        async with manager as session:
            value = await session.fetch(key)  # BENCH:critical
            if value is None:
                return None
            return await transform(value)
    except TimeoutError:
        return "timeout"


async def transform(value):
    return value
