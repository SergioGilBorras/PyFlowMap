from .rules import valid
def prepare(message):
    if not valid(message):
        raise ValueError("invalid")
    return message.strip()
