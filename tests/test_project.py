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


def test_zip_extraction_uses_managed_root_and_cleans_on_failure(tmp_path, monkeypatch):
    import pyflowmap.project as project_module

    archive = tmp_path / "code.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("src/worker.py", "def main(:\n")
    managed_parent = tmp_path / "managed"
    managed_parent.mkdir()
    monkeypatch.setenv("PYFLOWMAP_TEMP_ROOT", str(managed_parent))
    owners = []
    create = project_module.temporary_directory

    def track(namespace, parent=None, **kwargs):
        owner = create(namespace, parent=parent, **kwargs)
        owners.append(owner)
        return owner

    monkeypatch.setattr(project_module, "temporary_directory", track)
    with pytest.raises(ValueError, match="No parseable Python files found"), project_module.load_project(archive):
        pass

    assert len(owners) == 1
    assert owners[0].path.parent == managed_parent
    assert not owners[0].path.exists()


def test_zip_temp_parent_must_exist(tmp_path, monkeypatch):
    archive = tmp_path / "code.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("worker.py", "def main(): pass\n")
    monkeypatch.setenv("PYFLOWMAP_TEMP_ROOT", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="Temporary directory parent does not exist"), load_project(archive):
        pass


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
