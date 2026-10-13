class Gate:
    def __init__(self, quiet):
        self.quiet = quiet
    def __enter__(self):
        return self
    def __exit__(self, ty, error, traceback):
        if self.quiet and isinstance(error, ValueError):
            return True
        return False
def operate(quiet, reader):
    with Gate(quiet):
        if reader.empty():
            raise ValueError("empty")
        return reader.get()
    return "suppressed"
