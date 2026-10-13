async def refresh(sensor, cache):
    async with cache.transaction() as tx:
        try:
            reading = await sensor.read()
            if reading is None:
                return -1
            await tx.commit(reading)
            return 1
        except TimeoutError:
            await tx.rollback()
            return 0
        finally:
            sensor.mark_access()
