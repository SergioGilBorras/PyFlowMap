class Readable:
    def read(self):
        return "x"

class Writable:
    def write(self, value):
        return value

class Device(Readable, Writable):
    pass
