def find_match(items, permitted, record):
    for item in items:
        if (code := record(item)) and (permitted(code) or code.startswith("X")):
            return code
    return None
