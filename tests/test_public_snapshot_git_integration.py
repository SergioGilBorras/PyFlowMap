"""Integration regression for a read-only inventory of a *new temporary* Git repo."""

import hashlib
import json
import shutil
import subprocess

import pytest

from scripts.inventory_public_snapshot import main


@pytest.mark.skipif(shutil.which("git") is None, reason="Git unavailable")
def test_inventory_reads_real_git_objects_without_modifying_repository(tmp_path, monkeypatch, request):
    repo = tmp_path / "synthetic-repo"
    repo.mkdir()

    def restore_git_object_attributes():
        objects = repo / ".git" / "objects"
        if objects.is_dir():
            for path in objects.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    path.chmod(path.stat().st_mode | 0o200)

    request.addfinalizer(restore_git_object_attributes)

    def run(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    run("init", "-q")
    run("config", "user.name", "Synthetic Fixture")
    run("config", "user.email", "fixture@example.invalid")
    source = repo / "hello.py"
    payload = b"def hello():\n    return 'synthetic'\n"
    source.write_bytes(payload)
    run("add", "hello.py")
    run("commit", "-qm", "synthetic root")
    start = run("rev-parse", "HEAD")
    status_before = run("status", "--porcelain")
    monkeypatch.chdir(repo)
    result_path = tmp_path / "inventory.json"
    assert main(["--commit", start, "--output", str(result_path)]) == 0

    report = json.loads(result_path.read_text(encoding="utf-8"))
    assert report["source_commit"] == start
    assert report["safe_to_publish"] is False
    assert report["reviewed"] is False
    assert len(report["files"]) == 1
    item = report["files"][0]
    assert item["path"] == "hello.py"
    assert item["sha256"] == hashlib.sha256(payload).hexdigest()
    assert item["bytes"] == len(payload)
    assert item["review"] == "required"
    assert run("rev-parse", "HEAD") == start
    assert run("status", "--porcelain") == status_before
    assert run("rev-list", "--all", "--count") == "1"
