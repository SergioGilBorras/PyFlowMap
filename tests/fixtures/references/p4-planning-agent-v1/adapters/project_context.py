from typing import Any, Protocol
class ProjectContextAdapter(Protocol):
    def get_context(self, workspace: str) -> dict[str, Any]: ...
class MockProjectContextAdapter:
    def get_context(self, workspace: str) -> dict[str, Any]:
        return {}
