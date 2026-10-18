def allocate_seats(requests, limit):
    used = 0
    def reserve(count):
        nonlocal used
        if used + count > limit:
            return False
        used += count
        return True
    results = []
    for item in requests:
        if not reserve(item):
            return results
        results.append(item)
    return results
