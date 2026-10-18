def decode(record):
    match record:
        case {"kind": "event" | "update", "payload": [header, *body]} if header:
            return (header, body)
        case {"kind": "noop", **unused}:
            return None
        case ("error", str(message)):
            raise ValueError(message)
        case _:
            return False
