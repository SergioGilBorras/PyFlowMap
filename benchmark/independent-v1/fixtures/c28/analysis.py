def transform(item):
    return item * 2

def metrics(raw):
    values = [transform(x) for x in raw if x >= 0]
    delayed = (transform(x) for x in raw if x < 0)
    if not values:
        return ('empty', delayed)
    return ('filled', sum(values), delayed)
