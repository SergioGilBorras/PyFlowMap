class Indicator:
    @property
    def code(self):
        if self._source is None:
            raise RuntimeError("no sensor")
        return self._source.read_code()
def decide(indicator, handlers):
    action = handlers.get(indicator.code)
    if action is None:
        action = getattr(indicator, "fallback", None)
    return action(indicator) if action else "unknown"
