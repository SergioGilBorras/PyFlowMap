"""Repository checks for reproducible documentation and lean source distributions."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "benchmark").rglob("README.md")),
        ROOT / "scripts" / "README.md",
        ROOT / "output_validation" / "README.md",
        ROOT / "output_graphs" / "README.md"]


def test_documentation_relative_links_resolve():
    for source in DOCS:
        data = source.read_text(encoding="utf-8")
        for url in re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", data):
            if "://" in url or url.startswith(("mailto:", "#")):
                continue
            assert (source.parent / url).resolve().exists(), f"{source}: missing {url}"


def test_no_generated_or_installer_artifacts_in_tracked_source():
    assert not (ROOT / "Setup-PyFlowMap-Local.ps1").exists()
    assert not (ROOT / "examples" / "results").exists()
    assert {p.name for p in (ROOT / "benchmark").glob("*.py")} == {"__init__.py"}
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".serena/" in gitignore
    assert "output_validation/*" in gitignore
    assert "output_graphs/*" in gitignore
    assert not (ROOT / "examples" / "basic_pipeline.py").exists()
    assert not (ROOT / "examples" / "semantic_labeler_integration.py").exists()
    assert (ROOT / "output_validation" / "README.md").is_file()
    assert (ROOT / "output_graphs" / "README.md").is_file()
    assert "dist/" in gitignore
    assert "addopts = \"-p no:cacheprovider\"" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_regression_manifests_are_current_english_metadata():
    corpus = ROOT / "benchmark"
    baseline = json.loads((corpus / "cases.json").read_text(encoding="utf-8"))
    assert len(baseline["cases"]) == 15
    assert baseline["purpose"].startswith("Cross-domain")
    for folder, expected in (("independent-v1", 28), ("independent-v2", 30)):
        document = json.loads((corpus / folder / "cases.json").read_text(encoding="utf-8"))
        assert len(document["cases"]) == expected
        assert document["kind"] == "known-regression-corpus"
        assert document["parameters"]["language"] == "en"
        assert "generated" not in document


def test_developer_runners_explain_usage_in_english():
    commands = [
        [sys.executable, "-m", "benchmark.runners.run", "--help"],
        [sys.executable, "benchmark/independent-v1/run.py", "--help"],
        [sys.executable, "benchmark/independent-v2/run.py", "--help"],
        [sys.executable, "scripts/compare_labeler_modes.py", "--help"],
    ]
    for command in commands:
        result = subprocess.run(
            command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "--help" in result.stdout
        assert "language" in result.stdout.lower()
        assert not re.search(r"\b(ciega|primera ejecuci[oó]n|segunda ejecuci[oó]n|casos sin)\b",
                             result.stdout, flags=re.IGNORECASE)


def test_no_stale_benchmark_runner_paths_in_docs():
    for source in DOCS:
        data = source.read_text(encoding="utf-8")
        assert "benchmark/run.py" not in data, source
        assert "benchmark/metamorphic.py" not in data, source
        assert "benchmark/final-validation-1.0" not in data, source



def test_fresh_validation_runner_help_is_available_in_english():
    result = subprocess.run(
        [sys.executable, "scripts/run_full_validation.py", "--help"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--with-real-labeler" in result.stdout
    assert "--acknowledge-source-transmission" in result.stdout
    assert "--output-parent" in result.stdout
    assert "TEMP" in result.stdout


def test_live_inference_requires_explicit_acknowledgement():
    result = subprocess.run(
        [sys.executable, "scripts/compare_real_labeler.py",
         "--output", "never-create-this-output"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False, timeout=30,
    )
    assert result.returncode != 0
    assert "--acknowledge-source-transmission" in result.stderr
    assert not (ROOT / "never-create-this-output").exists()


def test_canonical_validation_exposes_explicit_codex_consent():
    result = subprocess.run(
        [sys.executable, "scripts/validate_all.py", "--help"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--acknowledge-source-transmission" in result.stdout


def test_global_validation_refuses_unacknowledged_inference():
    result = subprocess.run(
        [sys.executable, "scripts/validate_all.py"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=30,
    )
    assert result.returncode != 0
    assert "--acknowledge-source-transmission" in result.stderr
