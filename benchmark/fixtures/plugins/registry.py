"""Extensibility domain: dynamic dispatch and decorators (uncertain targets)."""


def validated(fn):
    def wrapper(*args, **kwargs):
        if not args:
            raise ValueError('missing args')
        return fn(*args, **kwargs)
    return wrapper


class Handler:
    def execute(self, payload):
        return payload


@validated
def dispatch(handler, payload):
    return handler.execute(payload)  # BENCH:critical
