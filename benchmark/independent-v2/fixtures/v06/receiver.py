async def consume_packets(stream, store):
    async with store.session() as session:
        async for packet in stream:
            if packet is None:
                break
            if packet.get("skip"):
                continue
            await session.write(packet)
        else:
            return "complete"
    return "interrupted"
