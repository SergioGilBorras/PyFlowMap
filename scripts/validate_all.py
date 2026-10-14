"""Run the complete two-mode validation and retain only the latest managed PASS.

All temporary work stays under OS TEMP. This script never cleans unrecognized
directories or overrides permissions, symlinks or Windows reparse points.
Real inference makes external authenticated Codex requests with source snippets.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output_validacion"
RUN_PATTERN = re.compile(r"validation-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[0-9a-f]{6}\Z")
CONTENTS = {
    ".pyflowmap-managed-validation.json", "validation-summary.json",
    "semantic-review-queue.md", "logs", "benchmark", "packaging",
}


def managed_run(path: Path, root: Path) -> bool:
    """Only recognize generated dated runs below the exact approved root."""
    if not path.is_dir() or not RUN_PATTERN.fullmatch(path.name):
        return False
    if path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ):
        return False
    if path.resolve().parent != root.resolve():
        return False
    marker = path / ".pyflowmap-managed-validation.json"
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if not (metadata.get("kind") == "pyflowmap-validation"
            and metadata.get("schema") == 1
            and metadata.get("run") == path.name):
        return False
    if {item.name for item in path.iterdir()} - CONTENTS:
        return False
    return True


def report_is_technically_complete(path: Path) -> tuple[bool, str]:
    summary_file = path / "validation-summary.json"
    real_file = path / "benchmark" / "codex" / "real-labeler-report.json"
    try:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        real = json.loads(real_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, f"Missing validation evidence: {exc}"
    if summary.get("run_kind") != "pyflowmap-validation":
        return False, "Unexpected validation provenance"
    if summary.get("modes") != ["disabled", "codex"]:
        return False, "Both provider modes are required"
    if any(step.get("status") != "PASS"
           for step in summary.get("steps", {}).values()):
        return False, "One or more validation steps failed"
    if not summary.get("steps") or summary.get("package", {}).get("status") != "PASS":
        return False, "Missing package or required steps"
    if len(real.get("cases", [])) != 81 or real.get("summary", {}).get("failed") != 0:
        return False, "81 real-inference cases are required without technical failures"
    if not (path / "semantic-review-queue.md").is_file():
        return False, "The semantic review queue is missing"
    return True, "TECHNICAL_PASS_SEMANTIC_REVIEW"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full deterministic + real-Codex evaluation, dated outputs, safe retention"
    )
    parser.add_argument(
        "--acknowledge-source-transmission", action="store_true",
        help="Required: authorize sending benchmark code excerpts to Codex"
    )
    args = parser.parse_args(argv)
    if not args.acknowledge_source_transmission:
        parser.error("Explicit --acknowledge-source-transmission is required")
    if (OUTPUT.is_symlink() or (OUTPUT.exists() and not OUTPUT.is_dir())
            or (OUTPUT.exists() and bool(
                getattr(OUTPUT.lstat(), "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)))):
        parser.error("Unsafe output_validacion directory")
    OUTPUT.mkdir(exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    name = f"validation-{stamp}_{uuid4().hex[:6]}"
    destination = OUTPUT / name
    command = [
        sys.executable, str(ROOT / "scripts" / "run_full_validation.py"),
        "--with-real-labeler", "--acknowledge-source-transmission",
        "--output-parent", str(OUTPUT), "--result-name", name,
    ]
    print(f"New validation: {destination}", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        print("Validation failed. Previous runs were NOT deleted.", file=sys.stderr)
        print(f"Investigate current report/logs in: {destination}", file=sys.stderr)
        return result.returncode
    ok, state = report_is_technically_complete(destination)
    if not ok:
        print(state + "; previous runs preserved.", file=sys.stderr)
        return 1
    warnings = []
    for previous in sorted(OUTPUT.iterdir()):
        if previous == destination or not previous.is_dir():
            continue
        if managed_run(previous, OUTPUT):
            try:
                shutil.rmtree(previous)
                print(f"Removed previous managed results: {previous.name}")
            except OSError as exc:
                warnings.append(f"Could not remove {previous.name}: {exc}")
        else:
            warnings.append(f"Preserved unrecognized directory: {previous.name}")
    print(f"VALIDATION: {state}")
    print(f"Latest results: {destination}")
    for warning in warnings:
        print("CLEANUP WARNING: " + warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
