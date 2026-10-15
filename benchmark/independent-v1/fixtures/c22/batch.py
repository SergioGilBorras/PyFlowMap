async def consume_stream(stream, sink):
    delivered = 0
    async for packet in stream:
        try:
            if not packet.valid:
                continue
            await sink.send(packet)
        except ConnectionError:
            break
        else:
            delivered += 1
    else:
        return ('complete', delivered)
    return ('interrupted', delivered)
