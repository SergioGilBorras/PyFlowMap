"""Run a fresh offline/static verification in OS TEMP without reusing results.

Never invokes the real Codex provider, modifies fixture sources, deletes previous
runs, or writes validation artifacts into the source checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
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
        report_file = output / "disabled" / suite / "report.json"
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
        report_file = output / "disabled" / suite / "run-report.json"
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
        "The mock labeler checks structure and integration, not truthfulness.",
        "",
    ])
    (output / "semantic-review-queue.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return lines, summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fresh PyFlowMap verification with all outputs under OS TEMP"
    )
    parser.add_argument(
        "--with-labeler", action="store_true",
        help="Additionally compare disabled/mock on all 73 cases (requires .[labeler]; no Codex)"
    )
    args = parser.parse_args(argv)

    if args.with_labeler and importlib.util.find_spec("p4_semantic_labeler") is None:
        parser.error("Install the optional extra first: python -m pip install -e '.[dev,mcp,labeler]'")
    if not shutil.which("dot"):
        parser.error("Graphviz 'dot' is required for full rendering tests")

    system_temp = original_system_temp()
    parent = system_temp / "pyflowmap-output"
    parent.mkdir(exist_ok=True)
    if not parent.resolve().is_relative_to(system_temp):
        parser.error("Output parent escapes system TEMP")
    output = Path(tempfile.mkdtemp(prefix="full-", dir=parent)).resolve()
    work = output / "work"
    work.mkdir()
    logs = output / "logs"
    logs.mkdir()

    environment = os.environ.copy()
    environment.update({
        "TEMP": str(work), "TMP": str(work), "TMPDIR": str(work),
        "PYFLOWMAP_TEMP_ROOT": str(work),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PIP_CACHE_DIR": str(work / "pip-cache"),
        "RUFF_CACHE_DIR": str(work / "ruff-cache"),
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
        disabled = output / "disabled"
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
        run("release-build", [
            py, "scripts/build_release.py", "--output", str(output / "packages"),
        ])
        if steps["release-build"]["status"] == "PASS":
            package = check_package(output / "packages", commit)
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
        "output": str(output),
        "modes": ["disabled", "mock"] if args.with_labeler else ["disabled"],
        "real_codex_inference": "NOT_RUN",
        "steps": steps,
        "semantic_evidence": statuses,
        "package": package,
        "new_checkout_temp_paths": new_paths,
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
