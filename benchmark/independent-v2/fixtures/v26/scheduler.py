async def execute_chain(job, notifier):
    try:
        if not await job.ready():
            return None
        return await notifier.publish(await job.result())
    except LookupError as exc:
        raise RuntimeError("missing") from exc
    finally:
        await job.close()
