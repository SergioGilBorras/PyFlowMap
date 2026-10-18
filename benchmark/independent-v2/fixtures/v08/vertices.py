def stream_vertices(rows, reporter):
    total = 0
    try:
        for row in rows:
            if row is None:
                continue
            total += 1
            yield from row
            if total > 5:
                break
        yield ("count", total)
    finally:
        reporter.closed(total)
