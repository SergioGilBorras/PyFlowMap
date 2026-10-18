"""Run a fresh offline/static verification in OS TEMP without reusing results.

Real Codex inference is explicit opt-in. This never deletes historical
runs or modifies fixture sources; scratch stays in OS TEMP.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def original_system_temp() -> Path:
    """Resolve the host TEMP, not a checkout-provided custom scratch path."""
    if os.name == "nt":
        selected = os.environ.get("TEMP")
        if not selected:
            raise RuntimeError("Windows TEMP must be configured")
        parent = Path(selected).expanduser().resolve()
    else:
        parent = Path(tempfile.gettempdir()).resolve()
    if not parent.is_dir() or parent.is_relative_to(ROOT):
        raise RuntimeError(f"Unsafe system temporary directory: {parent}")
    return parent


def unexpected_root_paths() -> set[str]:
    """Observe unexpected creations; never remove or attribute them to a tool."""
    return {p.name for p in ROOT.iterdir()
            if p.name.lower() == "_avast_" or p.name.startswith("pytest-cache-files-")}


def git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=False, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def check_package(output: Path, commit: str | None) -> dict:
    report_file = output / "release-build-report.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    errors = []
    if not commit or report.get("source_git_commit") != commit:
        errors.append("Package source commit is missing or mismatched")
    if report.get("clean_install_smoke", {}).get("status") != "PASS":
        errors.append("Installed-wheel smoke did not pass")
    artifacts = report.get("artifacts", {})
    if not artifacts or len(artifacts) != 2:
        errors.append("Expected wheel and sdist")
    for filename, metadata in artifacts.items():
        path = output / filename
        if not path.is_file() or sha256(path) != metadata.get("sha256"):
            errors.append(f"Missing or checksum-mismatched package: {filename}")
    return {"status": "FAIL" if errors else "PASS", "errors": errors,
            "files": sorted(artifacts)}


def collect_review(output: Path) -> tuple[list[str], dict]:
    lines = [
        "# Items requiring semantic review",
        "",
        "Automated structural/generation success is not semantic approval.",
        "Review exact JSON paths, labels, decisions and source references.",
        "",
    ]
    summaries = {}
    for suite in ("baseline", "control-flow"):
        report_file = output / "benchmark" / "disabled" / suite / "report.json"
        if not report_file.exists():
            lines.append(f"- {suite}: REPORT_MISSING")
            summaries[suite] = {"status": "NOT_VERIFIED"}
            continue
        report = json.loads(report_file.read_text(encoding="utf-8"))
        counts = Counter(row.get("status", "UNKNOWN") for row in report["cases"])
        summaries[suite] = dict(counts)
        for row in report["cases"]:
            if row.get("status") != "PASS":
                lines.append(
                    f"- {suite}/{row['id']}: {row.get('status', 'UNKNOWN')}; "
                    f"semantic={row.get('semantic_status', 'NOT_EVALUATED')}, "
                    f"structure={row.get('structural_status', 'UNKNOWN')}"
                )
    for suite in ("independent-v1", "independent-v2"):
        report_file = output / "benchmark" / "disabled" / suite / "run-report.json"
        if not report_file.exists():
            lines.append(f"- {suite}: REPORT_MISSING")
            summaries[suite] = {"status": "NOT_VERIFIED"}
            continue
        report = json.loads(report_file.read_text(encoding="utf-8"))
        counts = Counter(row.get("generation_status", "UNKNOWN")
                         for row in report["cases"])
        summaries[suite] = dict(counts)
        for row in report["cases"]:
            lines.append(
                f"- {suite}/{row['id']}: {row.get('semantic_status', 'NOT_EVALUATED')}; "
                f"generation={row.get('generation_status', 'UNKNOWN')}"
            )
    lines.extend([
        "",
        "The 58 independent-bank cases have no complete semantic oracle yet.",
        "Their GENERATED status never counts as semantic PASS.",
        "Real Codex label quality remains REVIEW until independently evaluated.",
        "",
    ])
    (output / "semantic-review-queue.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return lines, summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fresh validation: scratch in OS TEMP; outputs in TEMP or output_validation"
    )
    parser.add_argument(
        "--with-labeler", action="store_true",
        help="Additionally compare disabled/mock on all 73 cases (requires .[labeler]; no Codex)"
    )
    parser.add_argument("--with-real-labeler", action="store_true",
                        help="Real authenticated Codex inference across all 81 benchmark fixtures")
    parser.add_argument("--acknowledge-source-transmission", action="store_true",
                        help="Explicit authorization for sending source excerpts to Codex")
    parser.add_argument("--output-parent", type=Path,
                        help="Results parent: OS TEMP, or repo output_validation/")
    parser.add_argument("--result-name", help="Date-stamped destination name (for global validation)")
    args = parser.parse_args(argv)
    if args.with_real_labeler and args.with_labeler:
        parser.error("Select mock or real labeling, never both")
    if args.with_real_labeler and not args.acknowledge_source_transmission:
        parser.error("Real inference requires --acknowledge-source-transmission")
    if args.with_real_labeler:
        if not shutil.which("codex"):
            parser.error("Codex CLI unavailable; install Codex and authenticate")
        if os.environ.get("P4_LABELER_CODEX_WORKSPACE"):
            parser.error("Unset P4_LABELER_CODEX_WORKSPACE for isolated inference")

    if args.with_labeler and importlib.util.find_spec("p4_semantic_labeler") is None:
        parser.error("Install the optional extra first: python -m pip install -e '.[dev,mcp,labeler]'")
    if not shutil.which("dot"):
        parser.error("Graphviz 'dot' is required for full rendering tests")

    system_temp = original_system_temp()
    parent = (args.output_parent.expanduser().resolve() if args.output_parent
              else system_temp / "pyflowmap-output")
    checkout_outputs = (ROOT / "output_validation").resolve()
    if parent != checkout_outputs and not parent.is_relative_to(system_temp):
        parser.error("Output parent must be in OS TEMP or repo output_validation/")
    parent.mkdir(parents=True, exist_ok=True)
    if args.result_name:
        if not re.fullmatch(r"validation-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[0-9a-f]{6}", args.result_name):
            parser.error("--result-name must be a managed timestamped run name")
        output = parent / args.result_name
        output.mkdir(exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix="validation-", dir=parent)).resolve()
    (output / ".pyflowmap-managed-validation.json").write_text(
        json.dumps({"kind": "pyflowmap-validation", "schema": 1,
                    "run": output.name, "created_by": "scripts/run_full_validation.py"}) + "\n",
        encoding="utf-8",
    )
    work = Path(tempfile.mkdtemp(prefix="pyflowmap-work-", dir=system_temp)).resolve()
    logs = output / "logs"
    logs.mkdir()

    environment = os.environ.copy()
    environment.update({
        "TEMP": str(work), "TMP": str(work), "TMPDIR": str(work),
        "PYFLOWMAP_TEMP_ROOT": str(work),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "PIP_CACHE_DIR": str(work / "pip-cache"),
        "RUFF_CACHE_DIR": str(work / "ruff-cache"),
        "PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER": "disabled",  # pytest stays offline
    })
    for key in ("PIP_CACHE_DIR", "RUFF_CACHE_DIR"):
        Path(environment[key]).mkdir()
    commit = git_sha()
    before = unexpected_root_paths()
    steps: dict[str, dict] = {}
    py = sys.executable

    def run(name: str, argv: list[str]) -> None:
        log = logs / f"{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            stream.write("Command: " + " ".join(argv) + "\n\n")
            stream.flush()
            try:
                if name == "real-labeler":
                    # Forward each case to PowerShell as it completes; persist
                    # a duplicate in the log for offline troubleshooting.
                    with subprocess.Popen(
                        argv, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                        errors="replace", bufsize=1,
                    ) as live:
                        assert live.stdout is not None
                        for line in live.stdout:
                            stream.write(line)
                            stream.flush()
                            print(line, end="", flush=True)
                        rc = live.wait()
                else:
                    result = subprocess.run(
                        argv, cwd=ROOT, env=environment, stdout=stream,
                        stderr=subprocess.STDOUT, check=False, timeout=3600,
                    )
                    rc = result.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                stream.write("\nExecution error: " + str(exc) + "\n")
                rc = 124
        steps[name] = {"status": "PASS" if rc == 0 else "FAIL",
                       "exit_code": rc, "log": str(log)}
        print(f"{name}: {steps[name]['status']} (log: {log})", flush=True)

    try:
        run("pip-check", [py, "-m", "pip", "check"])
        run("pytest", [py, "-m", "pytest", "-q"])
        run("ruff", [py, "-m", "ruff", "check", "src", "tests", "scripts"])
        run("portable-tempdirs", [py, "scripts/verify_portable_tempdirs.py"])
        disabled = output / "benchmark" / "disabled"
        run("baseline", [py, "-m", "benchmark.runners.run", "--render",
                         "--output", str(disabled / "baseline")])
        run("control-flow", [
            py, "-m", "benchmark.runners.run",
            "--cases-file", "benchmark/control-flow/cases.json",
            "--fixtures-root", "benchmark/control-flow/fixtures",
            "--render", "--output", str(disabled / "control-flow"),
        ])
        run("metamorphic", [py, "-m", "benchmark.runners.metamorphic",
                            "--output", str(disabled / "metamorphic")])
        for bank in ("independent-v1", "independent-v2"):
            run(bank, [py, f"benchmark/{bank}/run.py", "--python", py,
                       "--project-root", str(ROOT),
                       "--output", str(disabled / bank)])
        if args.with_labeler:
            run("labeler-comparison", [
                py, "scripts/compare_labeler_modes.py", "--corpus", "all",
                "--output", str(output / "mock" / "comparison"),
            ])
            run("labeler-example", [py, "examples/semantic_labeler_integration.py"])
        if args.with_real_labeler:
            environment.setdefault("P4_LABELER_PROVIDER_TIMEOUT", "180")
            print(
                "Codex provider timeout per label: "
                f"{environment['P4_LABELER_PROVIDER_TIMEOUT']}s; "
                "one retry on ProviderTimeout",
                flush=True,
            )
            run("real-labeler", [
                py, "scripts/compare_real_labeler.py",
                "--acknowledge-source-transmission",
                "--output", str(output / "benchmark" / "codex"),
            ])
        run("release-build", [
            py, "scripts/build_release.py", "--output", str(output / "packaging"),
        ])
        if steps["release-build"]["status"] == "PASS":
            package = check_package(output / "packaging", commit)
        else:
            package = {"status": "NOT_VERIFIED", "errors": ["Build did not pass"]}
        _queue, statuses = collect_review(output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        steps["report-generation"] = {"status": "FAIL", "error": str(exc)}
        package = {"status": "NOT_VERIFIED", "errors": ["Report generation interrupted"]}
        statuses = {}
    new_paths = sorted(unexpected_root_paths() - before)
    summary = {
        "source_commit": commit,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "system_temp": str(system_temp),
        "temp_workspace": str(work),
        "output": str(output),
        "modes": (["disabled", "codex"] if args.with_real_labeler else
                  ["disabled", "mock"] if args.with_labeler else ["disabled"]),
        "real_codex_inference": "ATTEMPTED" if args.with_real_labeler else "NOT_RUN",
        "steps": steps,
        "semantic_evidence": statuses,
        "package": package,
        "new_checkout_temp_paths": new_paths,
        "real_label_semantic_fidelity": "REVIEW" if args.with_real_labeler else "NOT_EVALUATED",
        "run_kind": "pyflowmap-validation",
        "source_banks": {"baseline": 15, "control-flow": 8,
                         "independent-v1": 28, "independent-v2": 30},
    }
    (output / "validation-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    passed = (all(step["status"] == "PASS" for step in steps.values())
              and package["status"] == "PASS" and not new_paths)
    print(f"\nFull report: {output / 'validation-summary.json'}")
    print(f"Semantic review queue: {output / 'semantic-review-queue.md'}")
    if new_paths:
        print("New unexpected checkout paths (not deleted): " + ", ".join(new_paths))
    print("VALIDATION: " + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
