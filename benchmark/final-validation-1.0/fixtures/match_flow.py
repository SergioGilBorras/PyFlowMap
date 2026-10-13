def dispatch(record):
    match record:
        case {"kind": "put", "key": key, "value": value} if key:
            result = (key, value)
        case {"kind": "remove", "key": key}:
            result = (key, None)
        case _:
            return None

    match result:
        case (name, None):
            return remove(name)
        case (name, value):
            return write(name, value)  # BENCH:critical


def remove(name):
    return name


def write(name, value):
    return name, value
