"""Shared pytest fixtures and test isolation for tests/ and benchmark/.

Pytest automatically loads a root-level conftest.py. Keep this file at the
repository root so both test collections use the same temporary-space policy.
All scratch directories live in the OS temporary directory, never in Git.
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from portable_tempdirs import temporary_directory

_OWNER = None
_PREVIOUS_TEMP_ROOT: str | None = None
_PREVIOUS_SYSTEM_TEMP: dict[str, str | None] = {}


def _temporary_parent() -> Path:
    """Use the user's %TEMP% on Windows, or the configured POSIX temp root."""
    if os.name == "nt":
        selected = os.environ.get("TEMP")
        if not selected:
            raise RuntimeError("TEMP must name an existing writable directory on Windows")
    else:
        selected = tempfile.gettempdir()
    parent = Path(selected).expanduser().resolve()
    if not parent.is_dir():
        raise RuntimeError(f"System temporary directory does not exist: {parent}")
    return parent


def pytest_configure(config):
    """Allocate one managed test workspace outside the source checkout."""
    global _OWNER, _PREVIOUS_TEMP_ROOT
    if _OWNER is not None:
        return
    parent = _temporary_parent()
    # tempfile prefers TMPDIR/TEMP/TMP in that order. Do not let an inherited
    # TMPDIR or TMP pointing at the checkout create test scratch in source.
    for key in ("TMPDIR", "TMP"):
        _PREVIOUS_SYSTEM_TEMP[key] = os.environ.get(key)
        os.environ[key] = str(parent)
    _OWNER = temporary_directory("pyflowmap-pytest", parent=parent)
    _PREVIOUS_TEMP_ROOT = os.environ.get("PYFLOWMAP_TEMP_ROOT")
    os.environ["PYFLOWMAP_TEMP_ROOT"] = str(_OWNER.path)
    config.option.basetemp = str(_OWNER.path / "basetemp")


@pytest.fixture
def tmp_path():
    """Each test gets a unique disposable directory under the OS temp root.

    Default-mode directories inherit Windows TEMP ACLs rather than forcing
    pytest's restrictive owner-only ACL inside constrained environments.
    """
    if _OWNER is None:
        raise RuntimeError("pytest temporary directory owner is unavailable")
    parent = _OWNER.path / "test-workspaces"
    parent.mkdir(exist_ok=True)
    path = parent / f"t-{uuid.uuid4().hex}"
    path.mkdir()
    return path


def pytest_unconfigure(config):
    """Release the managed temporary workspace and restore environment."""
    global _OWNER, _PREVIOUS_TEMP_ROOT
    owner = _OWNER
    _OWNER = None
    try:
        if owner is not None:
            owner.cleanup()
    finally:
        if _PREVIOUS_TEMP_ROOT is None:
            os.environ.pop("PYFLOWMAP_TEMP_ROOT", None)
        else:
            os.environ["PYFLOWMAP_TEMP_ROOT"] = _PREVIOUS_TEMP_ROOT
        _PREVIOUS_TEMP_ROOT = None
        for key, old in _PREVIOUS_SYSTEM_TEMP.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        _PREVIOUS_SYSTEM_TEMP.clear()
