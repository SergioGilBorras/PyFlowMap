async def main(client):
    try:
        return await client.fetch()
    except TimeoutError:
        return None
