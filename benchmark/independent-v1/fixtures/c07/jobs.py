async def run_remote(session_factory, resource):
    async with session_factory() as session:
        try:
            result = await session.fetch(resource)
        except TimeoutError:
            return {'status': 'timeout'}
        else:
            return {'status': 'ok', 'data': result}
