def configure(limit, register):
    count = 0
    def callback(value):
        nonlocal count
        if value < limit:
            return False
        count += 1
        register(value)
        return count
    register(callback)
    return callback
