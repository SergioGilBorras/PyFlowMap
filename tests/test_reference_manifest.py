"""Pinned source snapshots are immutable and can coexist across versions."""

import hashlib
import json
from pathlib import Path

REFERENCE_ROOT = Path(__file__).parent / "fixtures" / "references"


def test_git_blob_hashes_match_pinned_source():
    manifest = json.loads((REFERENCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    for version, case in manifest["versions"].items():
        assert len(case["commit_sha"]) == 40, version
        snapshot = REFERENCE_ROOT / case["directory"]
        assert snapshot.is_dir()
        for relpath, expected_sha in case["blobs"].items():
            data = (snapshot / relpath).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            assert blob == expected_sha, f"{version}/{relpath}: snapshot diverged"
