"""Optional semantic providers only change labels, not decisions or graph provenance."""

import json
from pathlib import Path

from pyflowmap.service import generate_diagram


def _fixture(tmp_path: Path) -> None:
    (tmp_path / "work.py").write_text(
        "def collect_events():\n"
        "    \"\"\"Read events from the incoming queue.\"\"\"\n"
        "    return []\n"
        "def publish_events():\n"
        "    return None\n"
        "def main(ready=True):\n"
        "    if ready:\n"
        "        collect_events()\n"
        "    publish_events()\n",
        encoding="utf-8",
    )


def test_semantic_context_and_invariant(tmp_path):
    _fixture(tmp_path)
    original = generate_diagram(str(tmp_path), entry="work:main", format="mmd",
                                output=str(tmp_path / "base"))

    class Spy:
        def __init__(self):
            self.requests = []

        def label(self, request):
            self.requests.append(request)
            return f"Readable {request.symbols[0].split(':')[-1]}"

    provider = Spy()
    modified = generate_diagram(str(tmp_path), entry="work:main", format="mmd",
                                output=str(tmp_path / "labeled"), label_provider=provider)
    old = json.loads(Path(original["files"]["json"]).read_text())
    new = json.loads(Path(modified["files"]["json"]).read_text())
    assert provider.requests
    assert any(r.docstring == "Read events from the incoming queue."
               and "def collect_events" in r.source_snippet for r in provider.requests)
    assert any(r.following for r in provider.requests)
    assert all(r.language == "en" and r.filename == "work.py" for r in provider.requests)
    assert old["edges"] == new["edges"]
    assert [(n["id"], n["kind"], n["symbols"]) for n in old["nodes"]] == [
        (n["id"], n["kind"], n["symbols"]) for n in new["nodes"]]
    assert any(n["label_source"] == "external" for n in new["nodes"])
    assert all(n["label_source"] == "deterministic" for n in old["nodes"])
    assert all(n["label_source"] == "deterministic" for n in new["nodes"]
               if n["kind"] in ("decision", "initial", "final", "result"))


def test_invalid_external_label_and_exception_fall_back(tmp_path):
    _fixture(tmp_path)

    class Broken:
        def label(self, request):
            if "collect_events" in request.symbols[0]:
                return "<script>alert(1)</script>"
            raise RuntimeError("secret must not leak into errors")

    result = generate_diagram(str(tmp_path), entry="work:main", format="mmd",
                              output=str(tmp_path / "bad"), label_provider=Broken())
    doc = json.loads(Path(result["files"]["json"]).read_text())
    assert all(n["label_source"] == "deterministic" for n in doc["nodes"])
    assert any("Rejected invalid semantic label" in warning for warning in doc["warnings"])
    assert any("Semantic label unavailable" in warning for warning in doc["warnings"])
    assert "secret must not leak" not in json.dumps(doc)


def test_images_format_exports_both_images_and_editable_sources(tmp_path):
    _fixture(tmp_path)
    result = generate_diagram(str(tmp_path), entry="work:main", format="images",
                              output=str(tmp_path / "exports"), renderer="graphviz")
    assert result["renderer"] == "graphviz"
    assert set(result["files"]) == {"mmd", "json", "svg", "png"}
    assert Path(result["files"]["svg"]).read_text().find("<svg") >= 0
    assert Path(result["files"]["png"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

def test_reusable_pipeline_fixture_generates_own_artifacts(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "sample_project" / "pipeline.py"
    result = generate_diagram(
        str(fixture), entry="pipeline:main", format="mmd",
        output=str(tmp_path / "diagrams"),
    )
    assert set(result["files"]) == {"mmd", "json"}
    assert all(Path(filename).is_file() for filename in result["files"].values())
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert graph["nodes"] and graph["edges"]



def test_control_transfer_labels_remain_exact_under_external_provider(tmp_path):
    source = tmp_path / "control.py"
    source.write_text(
        "def main(value):\n"
        "    if value is None:\n"
        "        raise ValueError('missing')\n"
        "    return value.lower()\n",
        encoding="utf-8",
    )

    class AllLabels:
        def label(self, request):
            return "Generic whole-function summary"

    path = tmp_path / "enriched"
    result = generate_diagram(
        str(source), entry="control:main", format="mmd",
        output=str(path), max_nodes=40, max_depth=3,
        label_provider=AllLabels(),
    )
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    transfers = [node for node in graph["nodes"]
                 if node["kind"] == "activity"
                 and ("control_transfer" in node["label_metadata"]
                      or "generator_event" in node["label_metadata"])]
    assert transfers, "The regression fixture must cover an activity transfer"
    assert all(node["label_source"] == "deterministic" for node in transfers)
    assert all(node["label"] != "Generic whole-function summary" for node in transfers)
    assert any(node["label_source"] == "external" for node in graph["nodes"])
