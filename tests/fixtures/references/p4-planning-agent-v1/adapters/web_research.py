from typing import Protocol
class WebResearchAdapter(Protocol):
    def search(self, query: str) -> list[dict[str, str]]: ...
class MockWebResearchAdapter:
    def search(self, query: str) -> list[dict[str, str]]:
        return []
