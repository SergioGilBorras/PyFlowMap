from pathlib import Path
from zipfile import ZipFile

import pytest

from pyflowmap.project import load_project
from pyflowmap.service import inspect_project

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_inspection_and_entry_resolution():
    result = inspect_project(str(FIXTURE), scope="pipeline.py")
    ids = {symbol["id"] for symbol in result["symbols"]}
    assert "pipeline:main" in ids
    assert "pipeline:DataLoader.load" in ids
    with load_project(FIXTURE) as project:
        assert project.entry("pipeline:main").name == "main"
        assert project.entry("main").id == "pipeline:main"
        assert project.entry("task", scope="branching.py").id == "branching:task"
        with pytest.raises(ValueError, match="Unknown entry"):
            project.entry("does_not_exist")


def test_zip_source(tmp_path):
    archive = tmp_path / "code.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("src/worker.py", "def main():\n    save()\n")
    with load_project(archive) as project:
        assert project.entry("main").id == "src.worker:main"


def test_zip_rejects_traversal(tmp_path):
    archive = tmp_path / "code.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("../attack.py", "print('bad')")
    with pytest.raises(ValueError, match="Unsafe path"), load_project(archive):
        pass
    assert not (tmp_path / "attack.py").exists()


def test_ambiguous_point_of_entry(tmp_path):
    (tmp_path / "many.py").write_text("def alpha(): pass\ndef beta(): pass\n")
    with load_project(tmp_path) as project, pytest.raises(ValueError, match="No unambiguous"):
        project.entry(None)
