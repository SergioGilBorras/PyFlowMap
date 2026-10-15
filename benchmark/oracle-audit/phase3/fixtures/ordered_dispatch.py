"""Generic ordered case selection with a guard and a later same-pattern arm."""


def classify(value, enabled):
    match value:
        case "closed":
            reject()
        case "ready" if enabled(value):
            accept()
        case "ready":
            defer()
        case _:
            recover()
