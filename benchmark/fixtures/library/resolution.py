"""Python OO domain: overridden methods, method resolution and self dispatch."""


class Base:
    def convert(self, value):
        return value


class Derived(Base):
    def convert(self, value):
        if value is None:
            raise ValueError('missing')
        return value.lower()

    def process(self, value):
        return self.convert(value)  # BENCH:critical
