def shared_worker():
    if True:
        left_nested_action()


def handle(value):
    shared_worker()
    match value:
        case "left":
            left_action()
        case _:
            left_fallback()
