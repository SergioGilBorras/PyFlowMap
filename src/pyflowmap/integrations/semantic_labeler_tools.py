"""Small optional adapter for P4-Semantic-Labeler v0.1.0's PUBLIC Python API.

No service, HTTP transport or Codex execution is created here. Import lazily so
PyFlowMap remains usable with zero optional dependencies when disabled.
"""

import asyncio
from dataclasses import replace
from functools import lru_cache
from typing import Any

PROVIDERS = ("disabled", "mock", "codex")


def _imports():
    try:
        from p4_semantic_labeler import Context, Labeler, LabelRequest, Subject
        from p4_semantic_labeler.config import Settings
        from p4_semantic_labeler.core.models import BatchRequest
    except ImportError as exc:
        raise RuntimeError(
            "P4-Semantic-Labeler v0.1.0 is not installed. Install the optional "
            "PyFlowMap extra with `pip install '.[labeler]'` or `'.[labeler-codex]'`."
        ) from exc
    return Context, Labeler, LabelRequest, Subject, Settings, BatchRequest


class SemanticLabelerTools:
    """Reuse one Labeler instance for titles, summaries, async and batch calls.

    Callers receive the original P4 LabelResult / BatchResult, including all
    provider metadata and warnings. Errors are allowed to propagate unchanged.
    """

    def __init__(self, *, provider: str = "disabled", reduction_attempts: int = 1,
                 labeler: Any | None = None):
        if provider not in PROVIDERS:
            raise ValueError("provider must be disabled, mock or codex")
        if reduction_attempts < 0:
            raise ValueError("reduction_attempts must be >= 0")
        self.provider = provider
        self.reduction_attempts = reduction_attempts
        self._labeler = labeler

    def _client(self):
        if self.provider == "disabled":
            raise ValueError("Semantic labeling is disabled; explicitly select mock or codex")
        if self._labeler is None:
            _, Labeler, _, _, Settings, _ = _imports()
            # P4's default provider timeout is 20s. Honor the documented
            # P4_LABELER_PROVIDER_TIMEOUT (and other validated settings)
            # while keeping the caller's explicit provider selection.
            config = replace(
                Settings.from_env(),
                provider=self.provider,
                reduction_attempts=self.reduction_attempts,
            )
            self._labeler = Labeler(settings=config)
        return self._labeler

    @staticmethod
    def _request(*, name: str, kind: str = "function",
                 documentation: str | None = None, source_code: str | None = None,
                 text: str | None = None, before: str | None = None,
                 after: str | None = None, purpose: str | None = None,
                 module: str | None = None, class_name: str | None = None,
                 signature: str | None = None, max_chars: int = 80,
                 language: str = "en", style: str = "neutral",
                 output_type: str = "title"):
        Context, _, LabelRequest, Subject, _, _ = _imports()
        return LabelRequest(
            subject=Subject(name=name, kind=kind, module=module,
                            class_name=class_name, signature=signature),
            context=Context(documentation=documentation, source_code=source_code,
                            text=text, before=before, after=after, purpose=purpose),
            output_type=output_type, max_chars=max_chars, language=language, style=style)

    def generate_label(self, *, name: str, kind: str = "function",
                       documentation: str | None = None, source_code: str | None = None,
                       max_chars: int = 80, language: str = "en",
                       style: str = "neutral", **context):
        client = self._client()
        request = self._request(name=name, kind=kind, documentation=documentation,
                                source_code=source_code, max_chars=max_chars,
                                language=language, style=style, output_type="title", **context)
        return client.generate(request)

    def generate_summary(self, *, name: str, kind: str = "concept",
                         documentation: str | None = None, source_code: str | None = None,
                         max_chars: int = 160, language: str = "en",
                         style: str = "neutral", **context):
        client = self._client()
        request = self._request(name=name, kind=kind, documentation=documentation,
                                source_code=source_code, max_chars=max_chars,
                                language=language, style=style, output_type="summary", **context)
        return client.generate(request)

    async def agenerate_label(self, *, name: str, kind: str = "function",
                              documentation: str | None = None, source_code: str | None = None,
                              max_chars: int = 80, language: str = "en",
                              style: str = "neutral", **context):
        client = self._client()
        request = self._request(name=name, kind=kind, documentation=documentation,
                                source_code=source_code, max_chars=max_chars,
                                language=language, style=style, output_type="title", **context)
        return await client.agenerate(request)

    async def agenerate_labels_batch(self, items: list[dict[str, Any]]):
        client = self._client()
        *_, BatchRequest = _imports()
        requests = [self._request(**item) for item in items]
        return await client.agenerate_batch(BatchRequest(items=requests))

    def generate_labels_batch(self, items: list[dict[str, Any]]):
        """Synchronous convenience method; call async version inside event loops."""
        return asyncio.run(self.agenerate_labels_batch(items))


@lru_cache(maxsize=12)
def _shared(provider: str, reduction_attempts: int) -> SemanticLabelerTools:
    return SemanticLabelerTools(provider=provider, reduction_attempts=reduction_attempts)


def generate_label(*, provider: str = "disabled", reduction_attempts: int = 1, **kwargs):
    return _shared(provider, reduction_attempts).generate_label(**kwargs)


def generate_summary(*, provider: str = "disabled", reduction_attempts: int = 1, **kwargs):
    return _shared(provider, reduction_attempts).generate_summary(**kwargs)


async def agenerate_label(*, provider: str = "disabled", reduction_attempts: int = 1,
                          **kwargs):
    return await _shared(provider, reduction_attempts).agenerate_label(**kwargs)


def generate_labels_batch(items: list[dict[str, Any]], *, provider: str = "disabled",
                          reduction_attempts: int = 1):
    return _shared(provider, reduction_attempts).generate_labels_batch(items)
