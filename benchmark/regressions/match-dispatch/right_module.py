def shared_worker():
    if False:
        right_nested_action()


def handle(value):
    shared_worker()
    match value:
        case "right":
            right_action()
        case _:
            right_fallback()
