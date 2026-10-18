"""Network domain: async / await and timeout handling. No network requests are made."""

async def fetch_payload(client, key):
    return await client.get(key)

async def normalize(payload):
    return bool(payload)

async def handle(client, key):
    try:
        payload = await fetch_payload(client, key)  # BENCH:critical
        if await normalize(payload):  # BENCH:critical
            return {'status': 200}
        return {'status': 404}
    except TimeoutError:
        return {'status': 504}
