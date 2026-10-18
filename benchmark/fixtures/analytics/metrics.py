"""Numerical analysis domain: generator and comprehension with filtering."""


def normalize(x):
    return abs(x)


def summarize(values):
    cleaned = [normalize(x) for x in values if x is not None]  # BENCH:critical
    if not cleaned:
        return 0
    return sum(cleaned) / len(cleaned)
