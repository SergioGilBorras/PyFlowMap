def execute(worker, value):
    def prepare(item):
        return worker.normalize(item)

    result = prepare(value)
    if result:
        return worker.commit(result)  # BENCH:critical
    return None
