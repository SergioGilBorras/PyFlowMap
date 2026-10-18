def finalize(operation, sentinel):
    try:
        output = operation()
        if output is sentinel:
            return 'skipped'
        return 'ready'
    finally:
        if sentinel is None:
            return 'cancelled'
