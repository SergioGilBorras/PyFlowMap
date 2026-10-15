"""Contract-level tests for P4-Semantic-Labeler v0.1.0, no Codex inference.

The published API schema was inspected at git tag v0.1.0. These tests supply
lightweight doubles for that external package so PyFlowMap CI is not required to
authenticate to the separate private GitHub repository.
"""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import ClassVar

import pytest

from pyflowmap.integrations.semantic_labeler_tools import SemanticLabelerTools
from pyflowmap.service import generate_diagram


@pytest.fixture
def fake_p4(monkeypatch):
    @dataclass
    class Subject:
        name: str
        kind: str = "concept"
        module: str | None = None
        class_name: str | None = None
        signature: str | None = None

    @dataclass
    class Context:
        documentation: str | None = None
        source_code: str | None = None
        text: str | None = None
        before: str | None = None
        after: str | None = None
        purpose: str | None = None

    @dataclass
    class LabelRequest:
        subject: Subject
        context: Context
        output_type: str = "title"
        max_chars: int = 80
        language: str = "es"
        style: str = "neutral"

    @dataclass
    class Settings:
        provider: str = "disabled"
        reduction_attempts: int = 1

    @dataclass
    class BatchRequest:
        items: list = field(default_factory=list)

    class Labeler:
        instances: ClassVar[list] = []

        def __init__(self, settings=None):
            self.settings = settings
            self.calls = []
            self.__class__.instances.append(self)

        def generate(self, request):
            self.calls.append(request)
            return SimpleNamespace(
                label="Public label", char_count=12,
                language=request.language, style=request.style,
                output_type=request.output_type, provider=self.settings.provider,
                warnings=["mock_provider: synthetic name formatting, not semantic AI",
                          "output_truncated: meaning may be incomplete"],
            )

        async def agenerate(self, request):
            return self.generate(request)

        async def agenerate_batch(self, request):
            results = [await self.agenerate(item) for item in request.items]
            return SimpleNamespace(items=[SimpleNamespace(result=x) for x in results],
                                   success_count=len(results), error_count=0)

    api = ModuleType("p4_semantic_labeler")
    api.Subject, api.Context, api.LabelRequest, api.Labeler = Subject, Context, LabelRequest, Labeler
    config = ModuleType("p4_semantic_labeler.config")
    config.Settings = Settings
    core = ModuleType("p4_semantic_labeler.core")
    models = ModuleType("p4_semantic_labeler.core.models")
    models.BatchRequest = BatchRequest
    for mod in (api, config, core, models):
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
    yield Labeler


def test_library_sync_summary_async_and_batch(fake_p4):
    tools = SemanticLabelerTools(provider="mock", reduction_attempts=0)
    title = tools.generate_label(name="process_pending_orders", kind="method",
                                 documentation="Validate pending orders", max_chars=50,
                                 style="formal", language="es", module="order")
    assert title.label == "Public label"
    assert title.provider == "mock" and len(title.warnings) == 2
    instance = fake_p4.instances[-1]
    request = instance.calls[0]
    assert request.subject.kind == "method" and request.subject.module == "order"
    assert request.context.documentation == "Validate pending orders"
    assert request.max_chars == 50 and request.style == "formal"
    assert instance.settings.reduction_attempts == 0
    summary = tools.generate_summary(name="archive", text="Some text", max_chars=40)
    assert summary.output_type == "summary"
    assert asyncio.run(tools.agenerate_label(name="archive")).output_type == "title"
    batch = tools.generate_labels_batch([{"name": "one"}, {"name": "two"}])
    assert batch.success_count == 2
    assert len(fake_p4.instances) == 1  # client reused for every operation


def test_disabled_and_errors_not_silently_converted(fake_p4):
    tools = SemanticLabelerTools(provider="disabled")
    with pytest.raises(ValueError, match="disabled"):
        tools.generate_label(name="no_inference")

    class BadLabeler:
        def generate(self, request):
            raise RuntimeError("provider unavailable")

    failed = SemanticLabelerTools(provider="mock", labeler=BadLabeler())
    with pytest.raises(RuntimeError, match="provider unavailable"):
        failed.generate_label(name="name")


def test_diagram_with_mock_preserves_topology_and_warns(fake_p4, tmp_path):
    (tmp_path / "process.py").write_text(
        'def load_data():\n    """Loads input."""\n    return None\n'
        'def write_data():\n    return None\n'
        'def main(enabled=True):\n'
        '    if enabled:\n        load_data()\n    write_data()\n',
        encoding="utf-8")
    base = generate_diagram(str(tmp_path), entry="process:main",
                            output=str(tmp_path / "baseline"))
    mock = generate_diagram(str(tmp_path), entry="process:main", semantic_provider="mock",
                            semantic_style="academic", semantic_max_chars=40,
                            semantic_reduction_attempts=0,
                            output=str(tmp_path / "mock"))
    raw = json.loads(Path(base["files"]["json"]).read_text())
    enriched = json.loads(Path(mock["files"]["json"]).read_text())
    assert raw["edges"] == enriched["edges"]
    assert [(n["kind"], n["symbols"]) for n in raw["nodes"]] == [
        (n["kind"], n["symbols"]) for n in enriched["nodes"]]
    labeled = [n for n in enriched["nodes"] if n["label_source"] == "external"]
    assert labeled and all(n["label_metadata"]["external_label"]["provider"] == "mock"
                           for n in labeled)
    assert all(n["label_metadata"]["external_label"]["style"] == "academic"
               for n in labeled)
    assert any("output_truncated: meaning may be incomplete" in w for w in mock["warnings"])
    provider_warnings = [w for w in mock["warnings"] if w.startswith("Semantic provider warning:")]
    assert len(provider_warnings) == 2
    assert all(len(n["label_metadata"]["external_label"]["warnings"]) == 2 for n in labeled)
    by_id = {node["id"]: node for node in raw["nodes"]}
    for node in enriched["nodes"]:
        assert {key: value for key, value in node["label_metadata"].items()
                if key != "external_label"} == by_id[node["id"]]["label_metadata"]
    assert all(n["label_source"] == "deterministic" for n in enriched["nodes"]
               if n["kind"] == "decision")


def test_diagram_provider_failures_surface(fake_p4, tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text('def load_data():\n    return 1\n'
                                     'def main():\n    load_data()\n')

    def fail(*args, **kwargs):
        raise RuntimeError("temporary model error")

    monkeypatch.setattr(SemanticLabelerTools, "generate_label", fail)
    with pytest.raises(RuntimeError, match="P4 semantic labeling failed"):
        generate_diagram(str(tmp_path), entry="app:main",
                         semantic_provider="mock", output=str(tmp_path / "out"))


def test_cli_provider_option_is_explicit(fake_p4, tmp_path, capsys):
    from pyflowmap.cli import main

    (tmp_path / "app.py").write_text('def do_work():\n    return 1\n'
                                     'def main():\n    do_work()\n')
    assert main(["analyze", str(tmp_path), "--entry", "app:main",
                 "--semantic-provider", "mock", "--format", "mmd",
                 "--output", str(tmp_path / "cli")]) == 0
    assert '"semantic_provider": "mock"' in capsys.readouterr().out
