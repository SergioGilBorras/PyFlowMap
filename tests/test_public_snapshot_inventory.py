"""The public snapshot inventory is a read-only report, never publication approval."""

import hashlib
import json

import pytest

from scripts import inventory_public_snapshot as mod


def test_inventory_records_blob_hashes_but_requires_review(monkeypatch):
    payload = b"def example():\n    return 1\n"
    oid = "a" * 40
    calls = []

    def fake_git(*args):
        calls.append(args)
        if args[0] == "rev-parse":
            return ("b" * 40 + "\n").encode()
        if args[0] == "ls-tree":
            return f"100644 blob {oid}\tsrc/hello.py\0".encode()
        if args[0] == "cat-file":
            return payload
        raise AssertionError(args)

    monkeypatch.setattr(mod, "git", fake_git)
    result = mod.inventory("main")
    assert result["source_commit"] == "b" * 40
    assert result["safe_to_publish"] is False
    assert result["reviewed"] is False
    assert result["files"][0]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["files"][0]["review"] == "required"
    assert any(args[0] == "cat-file" for args in calls)


def test_inventory_blocks_symlinks_and_submodules(monkeypatch):
    tree = (b"120000 blob " + b"c" * 40 + b"\tlink\0"
            + b"160000 commit " + b"d" * 40 + b"\tmodule\0")

    def fake_git(*args):
        if args[0] == "rev-parse":
            return b"e" * 40 + b"\n"
        if args[0] == "ls-tree":
            return tree
        raise AssertionError("Must not read blocked entries")

    monkeypatch.setattr(mod, "git", fake_git)
    report = mod.inventory("main")
    assert len(report["files"]) == 2
    assert all("blocked" in row for row in report["files"])


def test_cli_does_not_overwrite_existing_report(tmp_path, monkeypatch):
    destination = tmp_path / "report.json"
    destination.write_text("private report", encoding="utf-8")
    monkeypatch.setattr(mod, "inventory", lambda _: {"files": [], "safe_to_publish": False})
    with pytest.raises(SystemExit):
        mod.main(["--commit", "main", "--output", str(destination)])
    assert destination.read_text(encoding="utf-8") == "private report"


def test_cli_writes_explicit_no_publish_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "inventory", lambda _: {
        "files": [], "safe_to_publish": False, "reviewed": False
    })
    destination = tmp_path / "inventory.json"
    assert mod.main(["--commit", "HEAD", "--output", str(destination)]) == 0
    assert json.loads(destination.read_text())["safe_to_publish"] is False
