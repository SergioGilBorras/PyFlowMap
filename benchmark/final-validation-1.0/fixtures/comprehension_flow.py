def collect(source):
    return [convert(value) for value in scan(source) if accepted(value)]


def scan(source):
    return source


def accepted(value):
    return bool(value)


def convert(value):
    return value
