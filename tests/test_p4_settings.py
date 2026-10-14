"""P4 environment settings must reach the real provider adapter."""

from dataclasses import dataclass

import pyflowmap.integrations.semantic_labeler_tools as adapter


def test_p4_timeout_from_environment_is_not_discarded(monkeypatch):
    monkeypatch.setenv("P4_LABELER_PROVIDER_TIMEOUT", "120")

    @dataclass(frozen=True)
    class StubSettings:
        provider: str = "disabled"
        reduction_attempts: int = 1
        provider_timeout_seconds: float = 20.0

        @classmethod
        def from_env(cls):
            import os

            return cls(provider_timeout_seconds=float(
                os.environ.get("P4_LABELER_PROVIDER_TIMEOUT", 20.0)
            ))

    class StubLabeler:
        def __init__(self, settings):
            self.settings = settings

    monkeypatch.setattr(
        adapter, "_imports",
        lambda: (object, StubLabeler, object, object, StubSettings, object),
    )
    tools = adapter.SemanticLabelerTools(provider="codex", reduction_attempts=2)
    client = tools._client()
    assert client.settings.provider == "codex"
    assert client.settings.reduction_attempts == 2
    assert client.settings.provider_timeout_seconds == 120.0
