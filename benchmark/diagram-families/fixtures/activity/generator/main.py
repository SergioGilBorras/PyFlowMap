def main(values):
    for value in values:
        if value:
            yield value
    yield from (1, 2)
