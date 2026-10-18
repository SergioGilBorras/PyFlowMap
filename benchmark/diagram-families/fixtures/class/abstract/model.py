from abc import ABC, abstractmethod

class Store(ABC):
    @abstractmethod
    def get(self, key: str) -> str:
        raise NotImplementedError

class MemoryStore(Store):
    @staticmethod
    def build():
        return MemoryStore()
