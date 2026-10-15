def receive_samples(source):
    try:
        value = yield "ready"
        while value is not None:
            if value < 0:
                value = yield "rejected"
                continue
            source.store(value)
            value = yield "accepted"
    except GeneratorExit:
        source.close()
        raise
    return "done"
