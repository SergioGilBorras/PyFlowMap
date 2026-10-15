def process(value):
    try:
        if value is None:
            return "empty"
        if invalid(value):
            raise ValueError(value)
        return normalize(value)
    finally:
        release(value)


def invalid(value):
    return value == "invalid"


def normalize(value):
    return str(value)


def release(value):
    return value
