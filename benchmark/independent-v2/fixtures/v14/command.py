def interpret_twice(raw, settings):
    match raw:
        case ["set", name, value] if name in settings:
            action = (name, value)
        case ["del", name]:
            action = (name, None)
        case _:
            return "invalid"
    match action:
        case ("mode", "safe"):
            return 1
        case (name, None) if name != "mode":
            return -1
        case _:
            return 0
