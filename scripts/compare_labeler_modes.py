"""Compare deterministic labels with the optional mock provider; never calls Codex."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(case: dict, provider: str, destination: Path, language: str = 'en') -> dict:
    source = (ROOT / "benchmark/fixtures" / case["source"]).resolve()
    if not source.is_relative_to((ROOT / "benchmark/fixtures").resolve()):
        raise ValueError(f"Fixture path escapes benchmark root: {case['source']}")
    output = destination / case["id"]
    args = [
        sys.executable, "-m", "pyflowmap", "analyze", str(source), "--entry", case["entry"],
        "--semantic-provider", provider, "--format", "mmd", "--renderer", "mermaid",
        "--language", language, "--output", str(output),
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{provider} failed for {case['id']}: {result.stderr[-1000:]}")
    cli = json.loads(result.stdout)
    graph_path = Path(cli["files"]["json"])
    return json.loads(graph_path.read_text(encoding="utf-8"))


def semantic_shape(graph: dict) -> dict:
    nodes = graph.get("nodes", [])
    return {
        "nodes": [{
            "id": node.get("id"),
            "kind": node.get("kind"),
            "symbols": node.get("symbols", []),
            "locations": node.get("locations", []),
            "semantic_metadata": {key: value for key, value in node.get("label_metadata", {}).items()
                                  if key != "external_label"},
            "decision_predicate": node.get("label") if node.get("kind") == "decision" else None,
        } for node in nodes],
        "edges": graph.get("edges", []),
        "semantic_warnings": [
            warning for warning in graph.get("warnings", [])
            if not str(warning).startswith(("Semantic provider warning:", "mock_provider:"))
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare disabled/mock semantic labels on the 15-case cross-domain regression bank")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "pyflowmap-output/labeler-comparison")
    parser.add_argument("--language", choices=["en", "es"], default="en",
                        help="Diagram label language (English by default)")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    cases = json.loads((ROOT / "benchmark/cases.json").read_text(encoding="utf-8"))["cases"]
    rows = []
    failures = []
    for case in cases:
        try:
            base = command(case, "disabled", output / "disabled", args.language)
            mock = command(case, "mock", output / "mock", args.language)
            same = semantic_shape(base) == semantic_shape(mock)
            external = [node for node in mock.get("nodes", []) if node.get("label_source") == "external"]
            labels = [str(node.get("label", "")) for node in external]
            label_warnings = [
                warning for node in external
                for warning in node.get("label_metadata", {}).get("external_label", {}).get("warnings", [])
            ]
            row = {
                "case": case["id"],
                "status": "PASS" if same else "FAIL",
                "structure_unchanged": same,
                "deterministic_nodes": len(base.get("nodes", [])),
                "mock_nodes": len(mock.get("nodes", [])),
                "deterministic_edges": len(base.get("edges", [])),
                "mock_edges": len(mock.get("edges", [])),
                "external_labels": len(labels),
                "empty_labels": sum(not value.strip() for value in labels),
                "labels_over_70_chars": sum(len(value) > 70 for value in labels),
                "label_lengths": [len(value) for value in labels],
                "deterministic_label_differences": sum(
                    node.get("label") != next(
                        (item.get("label") for item in base.get("nodes", [])
                         if item.get("id") == node.get("id")), None
                    ) for node in external
                ),
                "provider_warnings": label_warnings,
                "unsupported_text_claims": "not automatically decidable; requires human review",
            }
            rows.append(row)
            if not same:
                failures.append(case["id"])
        except Exception as exc:  # Preserve a per-case failure in the report.  # noqa: BLE001
            rows.append({"case": case["id"], "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
            failures.append(case["id"])
    report = {
        "provider_modes": ["disabled", "mock"],
        "language": args.language,
        "real_inference": "not run; no Codex provider invocation",
        "invariants": ["node IDs/kinds/symbols/locations", "edges", "semantic warnings"],
        "quality_scope": "empty/length/difference metrics only; factual grounding requires review",
        "cases": rows,
        "summary": {"cases": len(cases), "passed": len(cases) - len(failures),
                    "failed": len(failures), "failure_ids": failures},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "labeler-comparison.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
