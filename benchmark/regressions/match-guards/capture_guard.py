"""A successful pattern binds names before evaluating its guard."""


def route(message):
    match message:
        case {"payload": payload} if usable(payload):
            consume(payload)
        case _:
            skip()
