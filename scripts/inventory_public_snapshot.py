"""Read-only source snapshot inventory; does not export files or scan Git history."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(*args):
    return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def inventory(commit):
    resolved = git("rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    entries = []
    for record in git("ls-tree", "-rz", "--full-tree", resolved).split(b"\0"):
        if not record:
            continue
        header, path = record.split(b"\t", 1)
        mode, kind, blob_id = header.decode("ascii").split()
        filename = path.decode("utf-8", "surrogateescape")
        entry = {"path": filename, "mode": mode, "git_type": kind,
                 "git_oid": blob_id, "review": "required"}
        if kind != "blob" or mode not in ("100644", "100755"):
            entry["blocked"] = "submodule, symlink or unsupported Git mode"
        else:
            payload = git("cat-file", "blob", blob_id)
            entry["bytes"] = len(payload)
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
        entries.append(entry)
    return {"schema": 1, "source_commit": resolved, "files": entries,
            "reviewed": False, "safe_to_publish": False,
            "note": "Inventory only; not a secrets, license or history audit."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="Immutable source commit SHA/ref")
    parser.add_argument("--output", required=True, type=Path,
                        help="Local JSON report path; never commit an unreviewed report")
    args = parser.parse_args(argv)
    report = inventory(args.commit)
    if args.output.exists():
        parser.error("refusing to overwrite an existing inventory")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Inventory recorded: {len(report['files'])} paths; PUBLICATION NOT AUTHORIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
