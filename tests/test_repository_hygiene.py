"""Repository checks for reproducible documentation and lean source distributions."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "benchmark").glob("README.md")),
        *sorted((ROOT / "benchmark").rglob("README.md")),
        ROOT / "scripts" / "README.md"]


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
    assert not list(ROOT.glob("pytest-cache-files-*"))
    assert {p.name for p in (ROOT / "benchmark").glob("*.py")} == {"__init__.py"}
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".serena/" in gitignore
    assert "pyflowmap-output/" in gitignore
    assert "dist/" in gitignore
    assert "addopts = \"-p no:cacheprovider\"" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
