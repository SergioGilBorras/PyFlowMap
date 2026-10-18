def locate(items, target):
    for item in items:
        if item is None:
            continue
        if item == target:
            return item
        if should_stop(item):
            break
    else:
        return None
    return fallback(items)


def should_stop(item):
    return item == "stop"


def fallback(items):
    return items[-1] if items else None
