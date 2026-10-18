def values(source):
    try:
        for value in source:
            yield convert(value)
    except GeneratorExit:
        source.close()
        raise
    finally:
        notify("closed")


def convert(value):
    return value


def notify(message):
    return message
