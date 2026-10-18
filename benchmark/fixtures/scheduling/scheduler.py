"""Scheduling domain: nested lexical function, closure, loop and short circuit."""


def notify(task):
    return task


def schedule(tasks):
    completed = 0

    def run_one(task):
        if task is None:
            return False
        notify(task)  # BENCH:critical
        return True

    for task in tasks:
        if not run_one(task):  # BENCH:critical
            continue
        completed += 1
        if completed >= 3:
            break
    return completed
