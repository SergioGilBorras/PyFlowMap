"""Output contract and safe validation-retention regression tests."""

import json
import re
import runpy
from pathlib import Path

from pyflowmap.mcp_server import generate_diagram as mcp_generate
from pyflowmap.service import generate_diagram

ROOT = Path(__file__).resolve().parents[1]


def test_consumer_default_creates_unique_dated_folders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "workflow.py"
    source.write_text(
        "def main(value):\n    if value:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    outputs = []
    for _ in range(2):
        result = generate_diagram(
            str(source), entry="workflow:main", format="mmd",
            semantic_provider="disabled",
        )
        graph = Path(result["files"]["json"])
        assert graph.is_file()
        assert graph.with_suffix(".mmd").is_file()
        assert graph.parent.parent == tmp_path / "output_graphs"
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[a-f0-9]{8}",
            graph.parent.name,
        )
        outputs.append(graph.parent)
    assert outputs[0] != outputs[1]


def test_explicit_output_is_not_renamed(tmp_path):
    source = tmp_path / "input.py"
    source.write_text("def main():\n    return True\n", encoding="utf-8")
    destination = tmp_path / "explicit-output"
    result = generate_diagram(
        str(source), entry="input:main", output=str(destination),
        semantic_provider="disabled",
    )
    assert Path(result["files"]["json"]).parent == destination
    assert (destination / "input_main.mmd").is_file()


def test_mcp_uses_dated_default_within_allowed_workspace(tmp_path, monkeypatch):
    source = tmp_path / "input.py"
    source.write_text("def main():\n    return 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYFLOWMAP_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER", "disabled")
    result = mcp_generate(str(source), entry_point="input:main")
    assert Path(result["files"]["json"]).parent.parent == tmp_path / "output_graphs"


def test_only_owned_validation_runs_are_cleanup_candidates(tmp_path):
    util = runpy.run_path(str(ROOT / "scripts" / "validate_all.py"))
    managed = util["managed_run"]
    run = tmp_path / "validation-2026-10-14_17-10-00_abcdef"
    run.mkdir()
    (run / ".pyflowmap-managed-validation.json").write_text(
        json.dumps({
            "kind": "pyflowmap-validation", "schema": 1,
            "run": run.name, "created_by": "scripts/run_full_validation.py",
        }),
        encoding="utf-8",
    )
    assert managed(run, tmp_path)
    (run / "user_notes.txt").write_text("Preserve me", encoding="utf-8")
    assert not managed(run, tmp_path)
    (run / "user_notes.txt").unlink()
    assert not managed(tmp_path, tmp_path)
    marker = run / ".pyflowmap-managed-validation.json"
    marker.write_text('{"kind": "other"}', encoding="utf-8")
    assert not managed(run, tmp_path)
