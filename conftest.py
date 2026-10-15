"""Give every pytest frontend a private, owned basetemp in this checkout."""

import os
import uuid
from pathlib import Path

import pytest
from portable_tempdirs import temporary_directory

_OWNER = None
_PREVIOUS_TEMP_ROOT: str | None = None


def pytest_configure(config):
    """Allocate before pytest's tmp_path plugin initializes its factory."""
    global _OWNER, _PREVIOUS_TEMP_ROOT
    if _OWNER is not None:
        return
    # The checkout is explicitly writable in the active sandbox, so it is the
    # authorized parent for this run's owned directory and nested basetemp.
    project_root = Path(__file__).resolve().parent
    _OWNER = temporary_directory("pyflowmap-pytest", parent=project_root)
    _PREVIOUS_TEMP_ROOT = os.environ.get("PYFLOWMAP_TEMP_ROOT")
    os.environ["PYFLOWMAP_TEMP_ROOT"] = str(_OWNER.path)
    config.option.basetemp = str(_OWNER.path / "basetemp")


def pytest_sessionstart(session):
    """Bind pytest's already-created tmp_path factory to our owned directory."""
    if _OWNER is None:
        return
    basetemp = _OWNER.path / "basetemp"
    basetemp.mkdir()
    # The tmpdir plugin constructs its factory before conftest's configure
    # hook runs, so changing config.option alone does not update that factory.
    session.config._tmp_path_factory._basetemp = basetemp


@pytest.fixture
def tmp_path(request):
    """Create an isolated test directory inheriting the managed run's ACL.

    pytest's Windows tmp_path factory requests owner-only mode (0700). The
    Codex workspace sandbox denies writes to such child directories even when
    their portable-tempdirs parent is authorized. A unique default-mode child
    inherits the managed parent's ACL and remains private to this run.
    """
    if _OWNER is None:
        raise RuntimeError("pytest temporary directory owner is unavailable")
    path = _OWNER.path / "basetemp" / f"t-{uuid.uuid4().hex[:10]}"
    path.mkdir(parents=True)
    return path


def pytest_unconfigure(config):
    """Restore process state and propagate cleanup errors to pytest's caller."""
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
