"""P4 environment settings must reach the real provider adapter."""

from dataclasses import dataclass

import pytest

import pyflowmap.integrations.semantic_labeler_tools as adapter


@pytest.mark.parametrize(
    ("provider", "override", "expected"),
    [
        ("codex", None, 180.0),
        ("codex", "120", 120.0),
        ("codex", "300", 300.0),
        ("mock", None, 20.0),
    ],
)
def test_p4_timeout_from_environment_is_not_discarded(
    monkeypatch, provider, override, expected
):
    if override is None:
        monkeypatch.delenv("P4_LABELER_PROVIDER_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("P4_LABELER_PROVIDER_TIMEOUT", override)

    @dataclass(frozen=True)
    class StubSettings:
        provider: str = "disabled"
        reduction_attempts: int = 1
        provider_timeout_seconds: float = 20.0

        @classmethod
        def from_env(cls):
            import os

            return cls(provider_timeout_seconds=float(
                os.environ.get("P4_LABELER_PROVIDER_TIMEOUT", "20")
            ))

    class StubLabeler:
        def __init__(self, settings):
            self.settings = settings

    monkeypatch.setattr(
        adapter, "_imports",
        lambda: (object, StubLabeler, object, object, StubSettings, object),
    )
    tools = adapter.SemanticLabelerTools(provider=provider, reduction_attempts=2)
    client = tools._client()
    assert client.settings.provider == provider
    assert client.settings.reduction_attempts == 2
    assert client.settings.provider_timeout_seconds == expected
