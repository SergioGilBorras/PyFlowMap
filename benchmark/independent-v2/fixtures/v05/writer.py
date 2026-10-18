def atomic_publish(source, destination, guard):
    with guard.lock():
        with source.open("rb") as incoming, destination.open("wb") as outgoing:
            chunk = incoming.read(4096)
            if chunk == b"":
                return 0
            return outgoing.write(chunk)
