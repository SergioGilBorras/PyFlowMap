"""Resource domain: with and finalization on normal and exceptional paths."""

class Transaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def write_item(item):
    return len(item)


def store(item):
    with Transaction() as tx:
        if not item:
            return 'empty'
        write_item(item)  # BENCH:critical
    return 'stored'
