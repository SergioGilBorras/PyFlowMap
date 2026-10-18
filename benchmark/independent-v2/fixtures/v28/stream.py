async def measure(source, sink):
    count = 0
    try:
        async for reading in source:
            if reading is None:
                continue
            count += 1
            await sink.write(reading)
            yield count, reading
    finally:
        await sink.flush()
