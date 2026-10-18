"""Install the built release in a fresh venv using verified local dependencies.

The base development venv is only read. Installed distributions are copied to a
temporary wheelhouse after validating their installed RECORD digests; pip then
runs with --no-index in a second, clean venv outside the source checkout.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from xml.etree import ElementTree

from portable_tempdirs import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
PINNED_TEMP_DIRS_COMMIT = "fd6dbd640630e6911a53b4d756089099ec870a8b"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_installed_wheels(site: Path, wheelhouse: Path) -> list[dict]:
    """Repack installed distributions, rejecting any RECORD mismatch."""
    rows = []
    for dist in sorted(distributions(path=[str(site)]),
                       key=lambda item: (item.metadata.get("Name") or "").casefold()):
        name = dist.metadata.get("Name") or ""
        normalized = name.casefold().replace("_", "-").replace(".", "-")
        if normalized in {"pyflowmap", "p4-semantic-labeler"}:
            continue
        wheel_text = dist.read_text("WHEEL") or ""
        tags = re.findall(r"^Tag:\s*(\S+)", wheel_text, flags=re.MULTILINE)
        if not tags:
            continue
        members: dict[str, bytes] = {}
        for entry in dist.files or ():
            candidate = (site / str(entry)).resolve()
            if not candidate.is_relative_to(site) or not candidate.is_file():
                continue
            relative = candidate.relative_to(site).as_posix()
            if relative.endswith(".dist-info/RECORD"):
                continue
            data = candidate.read_bytes()
            recorded_hash = getattr(entry, "hash", None)
            if recorded_hash:
                actual_hash = base64.urlsafe_b64encode(
                    hashlib.new(recorded_hash.mode, data).digest()
                ).decode("ascii").rstrip("=")
                if actual_hash != recorded_hash.value:
                    raise ValueError(f"Installed RECORD digest mismatch: {name}/{relative}")
            members[relative] = data
        if not members:
            continue
        dist_info = Path(dist._path)
        for metadata_file in dist_info.rglob("*"):
            if metadata_file.is_file() and metadata_file.name != "RECORD":
                relative = metadata_file.relative_to(site).as_posix()
                members[relative] = metadata_file.read_bytes()
        record = io.StringIO(newline="")
        writer = csv.writer(record, lineterminator="\n")
        for relative, data in sorted(members.items()):
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            writer.writerow((relative, "sha256=" + digest.decode("ascii").rstrip("="), len(data)))
        record_path = dist_info.relative_to(site).as_posix() + "/RECORD"
        members[record_path] = record.getvalue().encode("utf-8")
        safe_name = re.sub(r"[^A-Za-z0-9_.]+", "_", name).lower().replace("-", "_")
        safe_version = re.sub(r"[^A-Za-z0-9_.]+", "_", dist.version)
        wheel_name = f"{safe_name}-{safe_version}-{tags[0]}.whl"
        wheel_path = wheelhouse / wheel_name
        with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, data in members.items():
                archive.writestr(relative, data)
        rows.append({"name": name, "version": dist.version, "wheel": wheel_name,
                     "sha256": _sha256(wheel_path), "bytes": wheel_path.stat().st_size,
                     "record_verified": True, "member_count": len(members)})
    return rows


def _run(report: dict, stage: str, command: list[str | Path], *, cwd: Path,
         env: dict[str, str], timeout: int = 240) -> bool:
    try:
        completed = subprocess.run(
            [str(value) for value in command], cwd=cwd, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
        output = (completed.stdout + "\n" + completed.stderr).strip()
        output = re.sub(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", output)
        report["stages"].append({"stage": stage, "command": [str(v) for v in command],
                                 "returncode": completed.returncode,
                                 "output_tail": output.splitlines()[-30:]})
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError, ValueError) as exc:  # preserve stage failures
        report["stages"].append({"stage": stage, "command": [str(v) for v in command],
                                 "error": f"{type(exc).__name__}: {exc}"})
        return False


def _probe_process(command: list[str | Path], *, cwd: Path, env: dict[str, str],
                   timeout: int) -> dict:
    """Capture exact launcher output and terminate only a timed-out child."""
    argv = [str(value) for value in command]
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        timed_out = True
    return {
        "command": argv,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "timeout_seconds": timeout,
    }


def _status_for_summary(verified: bool, launcher_status: str) -> str:
    """Only a successful executable launcher makes the full installation PASS."""
    if not verified or launcher_status not in {"PASS", "BLOCKED"}:
        return "FAIL"
    return "PARTIAL" if launcher_status == "BLOCKED" else "PASS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    wheel = args.wheel.resolve()
    work_parent = args.work_parent.expanduser().resolve()
    output = args.output.resolve()
    if not wheel.is_file() or not work_parent.is_dir():
        raise SystemExit("Wheel must exist and work-parent must be an existing directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "created_utc": datetime.now(UTC).isoformat(),
        "method": "Fresh Windows venv outside source; offline wheelhouse reconstructed from installed distributions and checked against RECORD.",
        "network": "pip --no-index; no downloads requested",
        "console_launcher": {"status": "NOT_RUN", "probes": []},
        "python": sys.version,
        "platform": sys.platform,
        "wheel": {"path": str(wheel), "sha256": _sha256(wheel), "bytes": wheel.stat().st_size},
        "work_parent": str(work_parent),
        "stages": [],
    }
    try:
        with temporary_directory("pyflowmap-offline-release", parent=work_parent) as workspace_text:
            workspace = Path(workspace_text)
            wheelhouse = workspace / "wheelhouse"
            wheelhouse.mkdir()
            site = Path(sys.prefix) / "Lib" / "site-packages"
            installed = {dist.metadata.get("Name", "").casefold().replace("_", "-"): dist
                         for dist in distributions(path=[str(site)])}
            portable = installed.get("portable-tempdirs")
            direct_url = json.loads(portable.read_text("direct_url.json") or "{}") if portable else {}
            commit = direct_url.get("vcs_info", {}).get("commit_id")
            report["portable_tempdirs"] = {"version": portable.version if portable else None,
                                             "commit": commit}
            if commit != PINNED_TEMP_DIRS_COMMIT:
                raise ValueError("Installed portable-tempdirs does not match the pinned commit")
            report["dependency_wheels"] = _write_installed_wheels(site, wheelhouse)
            report["stages"].append({"stage": "verified_wheelhouse", "status": "PASS",
                                     "wheel_count": len(report["dependency_wheels"])})
            venv = workspace / "clean-venv"
            env = os.environ.copy()
            for key in ("TEMP", "TMP", "TMPDIR"):
                env[key] = str(workspace)
            venv_ok = _run(report, "venv_creation", [sys.executable, "-m", "venv", "--without-pip", venv],
                           cwd=workspace, env=env)
            if venv_ok:
                python = venv / "Scripts" / "python.exe"
                env["PIP_CACHE_DIR"] = str(workspace / "pip-cache")
                (workspace / "pip-cache").mkdir()
                pip_ok = _run(report, "offline_pip_bootstrap", [
                    sys.executable, "-m", "pip", "--disable-pip-version-check", "--python", python,
                    "install", "--no-index", "--find-links", wheelhouse, "pip",
                ], cwd=workspace, env=env)
                if not pip_ok:
                    raise RuntimeError("Could not install verified pip wheel into the fresh venv")
                deps_ok = _run(report, "offline_dependency_install", [
                    python, "-m", "pip", "--disable-pip-version-check", "install", "--no-index",
                    "--find-links", wheelhouse, "portable-tempdirs==0.1.2", "mcp==2.3.0",
                ], cwd=workspace, env=env)
                if deps_ok:
                    wheel_ok = _run(report, "wheel_install", [
                        python, "-m", "pip", "--disable-pip-version-check", "install",
                        "--no-index", "--no-deps", wheel,
                    ], cwd=workspace, env=env)
                    if wheel_ok:
                        _run(report, "pip_check", [python, "-m", "pip", "check"], cwd=workspace, env=env)
                        entrypoint_probe = (
                            "from importlib.metadata import entry_points; "
                            "assert any(ep.name == 'pyflowmap' and ep.value == 'pyflowmap.cli:main' "
                            "for ep in entry_points(group='console_scripts')); "
                            "print('pyflowmap console entry point metadata available')"
                        )
                        _run(report, "console_entrypoint_metadata", [python, "-c", entrypoint_probe],
                             cwd=workspace, env=env)
                        help_env = env | {"PYTHONIOENCODING": "cp1252"}
                        cli = [python, "-m", "pyflowmap.cli"]
                        _run(report, "cli_help", cli + ["--help"],
                             cwd=workspace, env=help_env)
                        _run(report, "cli_version", cli + ["--version"],
                             cwd=workspace, env=env)
                        sample = workspace / "sample.py"
                        sample.write_text(
                            "def main():\n    if ready():\n        emit()\n"
                            "def ready():\n    return True\n"
                            "def emit():\n    return None\n", encoding="utf-8",
                        )
                        _run(report, "cli_all_formats", [
                            *cli, "analyze", sample, "--entry", "sample:main",
                            "--semantic-provider", "disabled", "--format", "all",
                            "--renderer", "graphviz", "--output", workspace / "artifacts",
                        ], cwd=workspace, env=env)
                        launcher = venv / "Scripts" / "pyflowmap.exe"
                        launcher_env = env.copy()
                        launcher_env.pop("PYTHONIOENCODING", None)
                        launcher_probes = [
                            _probe_process([launcher, "--help"], cwd=workspace,
                                           env=launcher_env, timeout=12),
                            _probe_process([launcher, "--version"], cwd=workspace,
                                           env=launcher_env, timeout=12),
                            _probe_process([
                                launcher, "analyze", sample, "--entry", "sample:main",
                                "--semantic-provider", "disabled", "--format", "all",
                                "--renderer", "graphviz", "--output", workspace / "launcher-artifacts",
                            ], cwd=workspace, env=launcher_env, timeout=45),
                        ]
                        report["console_launcher"] = {
                            "status": "PASS" if all(not item["timed_out"] and item["returncode"] == 0
                                                   for item in launcher_probes) else
                                      "BLOCKED" if any(item["timed_out"] for item in launcher_probes)
                                      else "FAIL",
                            "probes": launcher_probes,
                            "host_stdout_encoding": sys.stdout.encoding,
                        }
                        _run(report, "mcp_probe", [python, "-c",
                            "from pyflowmap.mcp_server import make_server; make_server(); print('MCP server available')"],
                             cwd=workspace, env=env)
                        artifacts = [path for path in (workspace / "artifacts").rglob("*") if path.is_file()]
                        suffixes = sorted({path.suffix.lower() for path in artifacts})
                        graph_paths = [path for path in artifacts if path.suffix.lower() == ".json"]
                        graph = json.loads(graph_paths[0].read_text(encoding="utf-8")) if graph_paths else {}
                        svg = next((path for path in artifacts if path.suffix.lower() == ".svg"), None)
                        png = next((path for path in artifacts if path.suffix.lower() == ".png"), None)
                        if svg:
                            ElementTree.parse(svg)
                        report["runtime_artifacts"] = {
                            "suffixes": suffixes,
                            "required_formats_present": all(ext in suffixes for ext in (".json", ".mmd", ".svg", ".png")),
                            "json_has_nodes_and_edges": bool(graph.get("nodes") and graph.get("edges")),
                            "svg_xml_valid": bool(svg),
                            "png_signature_valid": bool(png and png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")),
                        }
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        report["setup_error"] = f"{type(exc).__name__}: {exc}"
    failed = any(stage.get("returncode", 0) != 0 or "error" in stage for stage in report["stages"])
    artifacts = report.get("runtime_artifacts", {})
    verified = not failed and all(artifacts.get(key) for key in (
        "required_formats_present", "json_has_nodes_and_edges", "svg_xml_valid", "png_signature_valid"))
    report["status"] = _status_for_summary(verified, report["console_launcher"]["status"])
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(output),
                      "stages": [(stage.get("stage"), stage.get("returncode")) for stage in report["stages"]]},
                     ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
