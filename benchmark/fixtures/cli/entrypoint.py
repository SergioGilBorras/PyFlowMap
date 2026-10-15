"""Command-line domain: injected object, compound call receiver, distinct returns."""

class Worker:
    def execute(self, command):
        return bool(command)


def read_command():
    return 'run'


def main(worker=None):
    try:
        command = read_command()  # BENCH:critical
        result = (worker or Worker()).execute(command)  # BENCH:critical
        if not result:
            return 2
        return 0
    except ValueError:
        return 1
