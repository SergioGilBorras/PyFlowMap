def handle(group):
    try:
        raise group
    except* ValueError as errors:
        record_values(errors)
    except* TypeError as errors:
        record_types(errors)  # BENCH:critical
    finally:
        close_scope()


def record_values(errors):
    return errors


def record_types(errors):
    return errors


def close_scope():
    return None
