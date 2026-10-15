import os
import subprocess
import sys


def test_cli_help_is_printable_with_windows_cp1252_console():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [sys.executable, "-m", "pyflowmap.cli", "--help"],
        capture_output=True,
        text=True,
        encoding="cp1252",
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: pyflowmap" in result.stdout


def test_cli_version_uses_package_version():
    from pyflowmap import __version__

    result = subprocess.run(
        [sys.executable, "-m", "pyflowmap.cli", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"pyflowmap {__version__}"
