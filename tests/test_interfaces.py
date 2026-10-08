from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.mcp_server import generate_diagram, inspect_project
from pyflowmap.render import RenderError
from pyflowmap.service import generate_diagram as build

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_cli(tmp_path, capsys):
    assert main(["inspect", str(FIXTURE), "--scope", "pipeline.py"]) == 0
    assert "pipeline:main" in capsys.readouterr().out
    assert main(["analyze", str(FIXTURE), "--entry", "pipeline:main",
                 "--format", "mmd", "--output", str(tmp_path)]) == 0
    assert "pipeline_main.mmd" in capsys.readouterr().out


def test_renderer_missing_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr("pyflowmap.render.shutil.which", lambda executable: None)
    with pytest.raises(RenderError, match="npm install"):
        build(str(FIXTURE), entry="pipeline:main", format="svg", output=str(tmp_path))
    assert (tmp_path / "pipeline_main.mmd").exists()


def test_mcp_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("PYFLOWMAP_ALLOWED_ROOTS", str(FIXTURE.parent))
    assert inspect_project(str(FIXTURE), scope="pipeline.py")["symbols"]
    with pytest.raises(ValueError, match="outside allowed"):
        inspect_project(str(tmp_path))
    result = generate_diagram(str(FIXTURE), entry_point="pipeline:main",
                              output_path=str(FIXTURE.parent / "temp-out"))
    try:
        assert "flowchart TD" in result["mermaid"]
    finally:
        for name in result["files"].values():
            Path(name).unlink()
        (FIXTURE.parent / "temp-out").rmdir()
