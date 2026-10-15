class User:
    name: str
    _cache: str
    __token: str

    def __init__(self, name: str):
        self.name = name
        self._count: int = 0

    def _refresh(self):
        pass
