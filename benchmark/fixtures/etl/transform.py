"""Data engineering domain: iterable loop, skip, exception handler, else."""


def parse_record(row):
    return int(row)


def persist_record(value):
    return value


def process_batch(rows):
    accepted = 0
    for row in rows:
        if row is None:
            continue
        try:
            value = parse_record(row)  # BENCH:critical
        except ValueError:
            continue
        if value < 0:
            break
        persist_record(value)  # BENCH:critical
        accepted += 1
    else:
        accepted += 1
    return accepted
