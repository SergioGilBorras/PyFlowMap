"""Give every pytest frontend a private, owned basetemp in this checkout."""

import os
from pathlib import Path

from portable_tempdirs import temporary_directory

_OWNER = None
_PREVIOUS_TEMP_ROOT: str | None = None


def pytest_configure(config):
    """Allocate before pytest's tmp_path plugin initializes its factory."""
    global _OWNER, _PREVIOUS_TEMP_ROOT
    if _OWNER is not None:
        return
    project_root = Path(__file__).resolve().parent
    _OWNER = temporary_directory("pyflowmap-pytest", parent=project_root)
    _PREVIOUS_TEMP_ROOT = os.environ.get("PYFLOWMAP_TEMP_ROOT")
    os.environ["PYFLOWMAP_TEMP_ROOT"] = str(_OWNER.path)
    config.option.basetemp = str(_OWNER.path / "basetemp")


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
