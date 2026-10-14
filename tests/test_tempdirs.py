import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from portable_tempdirs import temporary_directory


def test_managed_tempdirs_are_isolated_and_cleaned_concurrently():
    workers = 4
    barrier = Barrier(workers)
    authorized_parent = tempfile.gettempdir()

    def allocate(_):
        with temporary_directory("pyflowmap-test", parent=authorized_parent) as name:
            barrier.wait(timeout=10)
            return name

    with ThreadPoolExecutor(max_workers=workers) as pool:
        names = list(pool.map(allocate, range(workers)))

    assert len(set(names)) == workers
    assert all(not Path(name).exists() for name in names)


def test_managed_tempdir_cleans_after_exception():
    allocated = None
    try:
        with temporary_directory("pyflowmap-test", parent=tempfile.gettempdir()) as name:
            allocated = Path(name)
            raise RuntimeError(name)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the body exception should propagate")

    assert allocated is not None and not allocated.exists()


def test_pytest_workspace_is_in_system_temp_not_checkout(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    expected = os.environ["TEMP"] if os.name == "nt" else tempfile.gettempdir()
    assert tmp_path.resolve().is_relative_to(Path(expected).resolve())
    assert not tmp_path.resolve().is_relative_to(project_root)
