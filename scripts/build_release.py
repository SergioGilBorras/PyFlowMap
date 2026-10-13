"""Build and smoke-test a clean local PyFlowMap wheel and sdist.

This script never uploads packages. Its temporary environment is created under
the requested output directory using portable-tempdirs and removed on exit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from portable_tempdirs import temporary_directory
from setuptools.build_meta import build_sdist, build_wheel

ROOT = Path(__file__).resolve().parents[1]
DENIED_PARTS = {
    ".git", ".serena", ".venv", "benchmark", "benchmark-results", "build",
    "dist", "docs", "examples", "pyflowmap-output", "scripts", "tests",
}


class _PortableBuildTemporaryDirectory:
    """Adapt setuptools' sdist staging directory to the managed sandbox ACL."""

    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False,
                 *, delete=True):
        if dir is None:
            raise ValueError("setuptools sdist staging must specify its build output directory")
        self._owner = temporary_directory("pyflowmap-sdist", parent=dir)
        self.name = str(self._owner.path)

    def __enter__(self):
        return self.name

    def __exit__(self, exc_type, exc, traceback):
        self.cleanup()
        return False

    def cleanup(self):
        self._owner.cleanup()
SDIST_ROOT_FILES = {
    "LICENSE", "MANIFEST.in", "PKG-INFO", "README.md", "pyproject.toml",
    "setup.cfg", "setup.py",
}
EGG_INFO_FILES = {
    "PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
    "requires.txt", "top_level.txt",
}


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=900,
    )
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {command!r}\n{completed.stdout}")
    return completed.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_release_members(path: Path, kind: str, expected_version: str) -> list[str]:
    if kind == "wheel":
        with zipfile.ZipFile(path) as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
            metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ValueError(f"Wheel must contain exactly one METADATA: {path}")
            metadata = archive.read(metadata_paths[0]).decode("utf-8")
            if f"Version: {expected_version}" not in metadata:
                raise ValueError(f"Wheel version mismatch in {path}")
            for member in names:
                if member.startswith("pyflowmap/"):
                    continue
                if member.startswith("pyflowmap-") and ".dist-info/" in member:
                    continue
                raise ValueError(f"Unexpected wheel content: {member}")
            for denied in ("tests/", "benchmark/", "docs/", ".serena/", "pyflowmap-output/"):
                if any(denied in member for member in names):
                    raise ValueError(f"Forbidden wheel content: {denied}")
            return names

    with tarfile.open(path, "r:gz") as archive:
        members = sorted(member.name for member in archive.getmembers() if member.isfile())
        if not members:
            raise ValueError(f"Empty source distribution: {path}")
        prefix = f"pyflowmap-{expected_version}/"
        for member in members:
            if not member.startswith(prefix):
                raise ValueError(f"Unexpected sdist root: {member}")
            relative = PurePosixPath(member[len(prefix):])
            if relative.parts and relative.parts[0] == "src":
                if len(relative.parts) == 3 and relative.parts[1] == "pyflowmap.egg-info" \
                        and relative.parts[2] in EGG_INFO_FILES:
                    continue
                if len(relative.parts) < 3 or relative.parts[1] != "pyflowmap":
                    raise ValueError(f"Unexpected source path in sdist: {member}")
                continue
            if relative.as_posix() not in SDIST_ROOT_FILES:
                if len(relative.parts) == 2 and relative.parts[0] == "pyflowmap.egg-info" \
                        and relative.parts[1] in EGG_INFO_FILES:
                    continue
                raise ValueError(f"Unexpected sdist content: {member}")
            if any(part in DENIED_PARTS for part in relative.parts):
                raise ValueError(f"Forbidden sdist content: {member}")
        metadata_path = next((member for member in members
                              if member.endswith("/PKG-INFO") and
                              (member == prefix + "PKG-INFO" or
                               member == prefix + "src/pyflowmap.egg-info/PKG-INFO")), None)
        pkg_info = archive.extractfile(metadata_path) if metadata_path else None
        if pkg_info is None or f"Version: {expected_version}" not in pkg_info.read().decode("utf-8"):
            raise ValueError(f"Sdist version mismatch in {path}")
        return members


def smoke_install(wheel: Path, work: Path, version: str) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    smoke_env = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        smoke_env[key] = str(work)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        smoke_env.pop(key, None)
    if os.name == "nt":
        # Git for Windows may not trust the active corporate/proxy CA in its
        # bundled OpenSSL store; Schannel uses the Windows certificate store.
        git_config = work / "release-smoke-gitconfig"
        git_config.write_text("[http]\n\tsslBackend = schannel\n", encoding="utf-8")
        smoke_env["GIT_CONFIG_GLOBAL"] = str(git_config)
    smoke_env["PIP_CACHE_DIR"] = str(work / "pip-cache")
    smoke_env["GIT_CEILING_DIRECTORIES"] = str(work)
    (work / "pip-cache").mkdir()
    venv = work / "clean-venv"
    sample = work / "sample-project"
    artifacts = work / "smoke-artifacts"
    sample.mkdir()
    (sample / "sample.py").write_text(
        "def main():\n    if ready():\n        emit()\n\ndef ready():\n    return True\n\ndef emit():\n    return None\n",
        encoding="utf-8",
    )
    run([sys.executable, "-m", "venv", str(venv)], env=smoke_env)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip = [str(python), "-m", "pip", "install", f"{wheel}[mcp]"]
    install_log = run(pip, cwd=work, env=smoke_env)
    cli = [str(python), "-m", "pyflowmap.cli"]
    help_env = os.environ.copy()
    help_env["PYTHONIOENCODING"] = "cp1252" if os.name == "nt" else "utf-8"
    help_env.update(smoke_env)
    help_output = run(cli + ["--help"], cwd=work, env=help_env)
    version_output = run(cli + ["--version"], cwd=work, env=smoke_env).strip()
    if version_output != f"pyflowmap {version}":
        raise ValueError(f"CLI version mismatch: {version_output}")
    run(cli + [
        "analyze", str(sample / "sample.py"), "--entry", "sample:main",
        "--semantic-provider", "disabled", "--format", "all", "--renderer", "graphviz",
        "--output", str(artifacts),
    ], cwd=work, env=smoke_env)
    generated = sorted(path for path in artifacts.rglob("*") if path.is_file())
    suffixes = {path.suffix.lower() for path in generated}
    if not {".json", ".mmd", ".svg", ".png"}.issubset(suffixes):
        raise ValueError(f"Missing output formats: {suffixes}")
    import json as json_module

    graph = next(path for path in generated if path.suffix == ".json")
    data = json_module.loads(graph.read_text(encoding="utf-8"))
    if not data.get("nodes") or not data.get("edges"):
        raise ValueError("Generated graph is empty")
    ElementTree.parse(next(path for path in generated if path.suffix == ".svg"))
    png = next(path for path in generated if path.suffix == ".png")
    if not png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature")
    mcp_probe = run([
        str(python), "-c",
        (
            "from importlib.metadata import entry_points; "
            "from pyflowmap.mcp_server import make_server; "
            "assert any(ep.name == 'pyflowmap-mcp' for ep in entry_points(group='console_scripts')); "
            "make_server(); print('MCP server available')"
        ),
    ], cwd=work, env=smoke_env)
    return {
        "install_command": pip,
        "install_log_tail": install_log.splitlines()[-12:],
        "cli_help_excerpt": help_output.splitlines()[:4],
        "cli_version": version_output,
        "outputs": [path.name for path in generated],
        "mcp_probe": mcp_probe.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and verify local PyFlowMap release artifacts")
    parser.add_argument("--output", type=Path, help="Release output directory (default: official validation folder)")
    parser.add_argument("--work-parent", type=Path, default=ROOT,
                        help="Authorized parent for temporary staging and the clean install venv")
    args = parser.parse_args(argv)
    output = (args.output or ROOT / "pyflowmap-output/final-validation-1.0/07-release").resolve()
    output.mkdir(parents=True, exist_ok=True)
    work_parent = args.work_parent.expanduser().resolve()
    if not work_parent.is_dir():
        raise SystemExit(f"Temporary work parent must already exist: {work_parent}")
    from pyflowmap import __version__

    if __version__ != "1.0.0":
        raise SystemExit(f"Expected release version 1.0.0, found {__version__}")
    for old in output.glob("pyflowmap-1.0.0*"):
        if old.is_file():
            old.unlink()
    with temporary_directory("pyflowmap-release-smoke", parent=work_parent) as temporary:
        workspace = Path(temporary)
        build_output = workspace / "dist"
        build_output.mkdir()
        staging = workspace / "source"
        staging.mkdir()
        for name in ("README.md", "LICENSE", "pyproject.toml", "MANIFEST.in"):
            shutil.copy2(ROOT / name, staging / name)
        shutil.copytree(ROOT / "src/pyflowmap", staging / "src/pyflowmap",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        original_cwd = Path.cwd()
        try:
            os.chdir(staging)
            original_temporary_directory = tempfile.TemporaryDirectory
            tempfile.TemporaryDirectory = _PortableBuildTemporaryDirectory
            try:
                sdist_name = build_sdist(str(build_output))
                wheel_name = build_wheel(str(build_output))
            finally:
                tempfile.TemporaryDirectory = original_temporary_directory
        finally:
            os.chdir(original_cwd)
        build_log = f"PEP 517 backend created {sdist_name} and {wheel_name}"
        built_wheel, built_sdist = build_output / wheel_name, build_output / sdist_name
        wheel_members = ensure_release_members(built_wheel, "wheel", __version__)
        sdist_members = ensure_release_members(built_sdist, "sdist", __version__)
        wheel, sdist = output / wheel_name, output / sdist_name
        shutil.copy2(built_wheel, wheel)
        shutil.copy2(built_sdist, sdist)
        try:
            smoke = {"status": "PASS", **smoke_install(built_wheel, workspace / "smoke", __version__)}
        except Exception as exc:  # noqa: BLE001 - persist any smoke failure in the release report.
            smoke = {"status": "FAIL", "error": f"{type(exc).__name__}: {str(exc)[:3000]}"}
    report = {
        "version": __version__,
        "python": sys.version,
        "platform": sys.platform,
        "graphviz": shutil.which("dot"),
        "output": str(output),
        "build_log_tail": build_log.splitlines()[-12:],
        "artifacts": {
            wheel.name: {"sha256": sha256(wheel), "bytes": wheel.stat().st_size, "members": wheel_members},
            sdist.name: {"sha256": sha256(sdist), "bytes": sdist.stat().st_size, "members": sdist_members},
        },
        "clean_install_smoke": smoke,
        "semantic_provider": "disabled",
    }
    (output / "release-build-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"version": __version__, "wheel": wheel.name, "sdist": sdist.name,
                      "output": str(output), "clean_install_status": smoke["status"]}, indent=2))
    return 0 if smoke["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
