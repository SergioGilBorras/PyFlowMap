"""Public example source remains runnable as a static-analysis input."""

import json
from pathlib import Path

from pyflowmap import service


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "basic_pipeline.py"


def test_basic_pipeline_example_is_self_contained(tmp_path):
    symbols = service.inspect_project(str(EXAMPLE))["symbols"]
    assert any(symbol["id"] == "basic_pipeline:main" for symbol in symbols)

    result = service.generate_diagram(
        str(EXAMPLE),
        entry="basic_pipeline:main",
        format="mmd",
        output=str(tmp_path / "diagrams"),
    )
    assert set(result["files"]) == {"mmd", "json"}
    assert all(Path(path).is_file() for path in result["files"].values())
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert graph["nodes"] and graph["edges"]
