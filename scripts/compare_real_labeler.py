"""Evaluate the REAL P4/Codex labeler over every retained Python corpus.

This explicitly transmits selected code excerpts to Codex. Each selected case
is analyzed once with deterministic labels and once with authenticated Codex.
Reports distinguish structure/provenance PASS from human semantic-quality REVIEW.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from compare_labeler_modes import cases_for, semantic_shape

ROOT = Path(__file__).resolve().parents[1]


def all_cases() -> list[dict]:
    cases = cases_for("all")
    control = json.loads(
        (ROOT / "benchmark/control-flow/cases.json").read_text(encoding="utf-8")
    )["cases"]
    for case in control:
        cases.append({
            **case, "suite": "control-flow", "id": "control-flow-" + case["id"],
        })
    return cases


def analyze(case: dict, provider: str, root: Path, timeout: int) -> dict:
    source_roots = {
        "baseline": ROOT / "benchmark/fixtures",
        "independent-v1": ROOT / "benchmark/independent-v1",
        "independent-v2": ROOT / "benchmark/independent-v2",
        "control-flow": ROOT / "benchmark/control-flow/fixtures",
    }
    source_root = source_roots[case["suite"]].resolve()
    source = (source_root / case["source"]).resolve()
    if not source.is_relative_to(source_root) or not source.exists():
        raise ValueError("Fixture source is missing or escapes its bank")
    output = root / provider / case["id"]
    argv = [
        sys.executable, "-m", "pyflowmap.cli", "analyze", str(source),
        "--entry", case["entry"], "--semantic-provider", provider,
        "--language", "en", "--max-nodes", "30", "--max-depth", "3",
        "--format", "all", "--renderer", "graphviz",
        "--output", str(output),
    ]
    process = subprocess.run(
        argv, cwd=ROOT, env=os.environ.copy(), capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False, timeout=timeout,
    )
    if process.returncode:
        # The CLI can emit provider/installation errors; do not echo code excerpts.
        raise RuntimeError(f"{provider} analysis returned {process.returncode}: "
                           f"{process.stderr[-700:]}")
    result = json.loads(process.stdout)
    paths = result.get("files", {})
    graph = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    for ext in ("json", "mmd", "svg", "png"):
        path = Path(paths[ext])
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing output format {ext}")
    return graph


def run_case(case: dict, root: Path, timeout: int) -> tuple[dict, list[dict]]:
    base = analyze(case, "disabled", root, timeout)
    labeled = analyze(case, "codex", root, timeout)
    unchanged = semantic_shape(base) == semantic_shape(labeled)
    original = {node["id"]: node for node in base["nodes"]}
    review = []
    for node in labeled["nodes"]:
        if node.get("label_source") != "external":
            continue
        metadata = node.get("label_metadata", {}).get("external_label", {})
        review.append({
            "case": case["id"], "suite": case["suite"], "node_id": node["id"],
            "symbols": ";".join(node.get("symbols", [])),
            "locations": ";".join(node.get("locations", [])),
            "deterministic_label": original.get(node["id"], {}).get("label", ""),
            "codex_label": node.get("label", ""),
            "provider": metadata.get("provider"),
            "warnings": ";".join(map(str, metadata.get("warnings", []))),
            "semantic_fidelity": "REVIEW",
        })
    authentic = bool(review) and all(row["provider"] == "codex" for row in review)
    well_formed = all(
        row["codex_label"].strip() and len(row["codex_label"]) <= 70
        for row in review
    )
    passed = unchanged and authentic and well_formed
    summary = {
        "case": case["id"], "suite": case["suite"],
        "status": "PASS" if passed else "FAIL",
        "topology_and_provenance_unchanged": unchanged,
        "real_codex_labels": len(review),
        "provider_verified": authentic,
        "labels_well_formed": well_formed,
        "semantic_fidelity": "REVIEW",
        "deterministic_nodes": len(base["nodes"]),
        "codex_nodes": len(labeled["nodes"]),
        "deterministic_edges": len(base["edges"]),
        "codex_edges": len(labeled["edges"]),
    }
    return summary, review


def save(root: Path, cases: list[dict], rows: list[dict],
         reviews: list[dict]) -> None:
    failures = [row["case"] for row in rows if row["status"] != "PASS"]
    report = {
        "provider_modes": ["disabled", "codex"],
        "real_inference": "Codex invoked for successful codex-labeled cases",
        "scope": "81 benchmark programs; labels require human review",
        "cases_requested": len(cases),
        "cases_completed": len(rows),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "cases": rows,
        "summary": {"passed": len(rows)-len(failures), "failed": len(failures),
                    "failure_ids": failures},
    }
    (root / "real-labeler-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (root / "label-quality-review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as out:
        fields = [
            "case", "suite", "node_id", "symbols", "locations",
            "deterministic_label", "codex_label", "provider",
            "warnings", "semantic_fidelity",
        ]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reviews)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Live Codex labels for 81 regression cases"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--acknowledge-source-transmission", action="store_true",
        help="Required: send selected code excerpts to authenticated Codex"
    )
    parser.add_argument("--timeout-per-case", type=int, default=3600,
                        help="Per subprocess time limit in seconds (outer safety bound)")
    parser.add_argument("--only", nargs="*",
                        help="Optional subset by exact case ID for diagnostics")
    args = parser.parse_args(argv)
    if not args.acknowledge_source_transmission:
        parser.error("Real inference requires --acknowledge-source-transmission")
    if not shutil.which("codex"):
        parser.error("Codex CLI not found on PATH; install it and run 'codex login'")
    if not shutil.which("dot"):
        parser.error("Graphviz dot not found on PATH")
    if args.timeout_per_case <= 0:
        parser.error("--timeout-per-case must be positive")
    try:
        import p4_codex_bridge  # noqa: F401 - explicit real-provider dependency preflight
        import p4_semantic_labeler  # noqa: F401
    except ImportError as exc:
        parser.error(f"Install PyFlowMap's [labeler-codex] extra: {exc}")
    if os.environ.get("P4_LABELER_CODEX_WORKSPACE"):
        parser.error("Unset P4_LABELER_CODEX_WORKSPACE for isolated Codex workspaces")
    cases = all_cases()
    if args.only:
        selection = set(args.only)
        available = {case["id"] for case in cases}
        if selection - available:
            parser.error("Unknown case IDs: " + ", ".join(sorted(selection-available)))
        cases = [case for case in cases if case["id"] in selection]
    destination = args.output.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        parser.error("Output directory is not empty; supply a fresh location")
    destination.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    review: list[dict] = []
    for index, case in enumerate(cases, 1):
        began = time.monotonic()
        print(f"[{index}/{len(cases)}] START {case['id']} (disabled then real Codex)",
              flush=True)
        try:
            row, labels = run_case(case, destination, args.timeout_per_case)
            review.extend(labels)
        except (OSError, RuntimeError, ValueError, KeyError,
                subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            message = str(exc)
            kind = ("PROVIDER_TIMEOUT" if "ProviderTimeout" in message else
                    "SUBPROCESS_TIMEOUT" if isinstance(exc, subprocess.TimeoutExpired) else
                    "PROVIDER_ERROR" if "P4 semantic labeling failed" in message else
                    "ANALYSIS_ERROR")
            row = {
                "case": case["id"], "suite": case["suite"],
                "status": "FAIL", "failure_type": kind,
                "error": f"{type(exc).__name__}: {message[:1000]}",
                "semantic_fidelity": "NOT_EVALUATED",
            }
        row["elapsed_seconds"] = round(time.monotonic() - began, 2)
        rows.append(row)
        save(destination, cases, rows, review)
        explanation = f" ({row['failure_type']})" if row.get("failure_type") else ""
        print(f"[{index}/{len(cases)}] END {case['id']} = {row['status']}"
              f"{explanation} in {row['elapsed_seconds']}s", flush=True)
    return 0 if all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
