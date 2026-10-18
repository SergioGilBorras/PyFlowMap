def audit(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            publish_event(fn.__name__)
    return wrapper
def cache(fn):
    def wrapper(key):
        if key in MEMORY:
            return MEMORY[key]
        result = fn(key)
        MEMORY[key] = result
        return result
    return wrapper
@audit
@cache
def perform(key):
    return read_value(key)
