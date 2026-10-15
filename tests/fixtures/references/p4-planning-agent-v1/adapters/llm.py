from typing import Protocol
class LLMAdapter(Protocol):
    def complete(self, prompt: str) -> str: ...
class MockLLMAdapter:
    def complete(self, prompt: str) -> str:
        return "External calls disabled."
