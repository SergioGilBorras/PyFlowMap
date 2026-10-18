"""Immutable, independently authored synthetic static-analysis fixtures."""

import ast
import hashlib
import json
from pathlib import Path

REFERENCE_ROOT = Path(__file__).parent / "fixtures" / "references"


def test_synthetic_fixture_blobs_match_manifest():
    manifest = json.loads((REFERENCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert set(manifest["fixtures"]) == {"synthetic-activity-regression-v1"}

    for version, case in manifest["fixtures"].items():
        assert case["origin"].startswith("independently authored synthetic"), version
        snapshot = REFERENCE_ROOT / case["directory"]
        assert snapshot.is_dir()
        assert len(case["files"]) == len(case["blobs"]) == 10
        assert set(case["files"]) == set(case["blobs"])
        assert {str(p.relative_to(snapshot)).replace("\\", "/")
                for p in snapshot.rglob("*.py")} == set(case["files"])
        for relpath, expected_sha in case["blobs"].items():
            data = (snapshot / relpath).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            assert blob == expected_sha, f"{version}/{relpath}: synthetic source diverged"
            ast.parse(data.decode("utf-8"), filename=relpath)
