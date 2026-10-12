from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from portable_tempdirs import temporary_directory


def test_managed_tempdirs_are_isolated_and_cleaned_concurrently(tmp_path):
    workers = 4
    barrier = Barrier(workers)

    def allocate(_):
        with temporary_directory("pyflowmap-test", parent=tmp_path) as name:
            barrier.wait(timeout=10)
            return name

    with ThreadPoolExecutor(max_workers=workers) as pool:
        names = list(pool.map(allocate, range(workers)))

    assert len(set(names)) == workers
    assert list(tmp_path.iterdir()) == []


def test_managed_tempdir_cleans_after_exception(tmp_path):
    try:
        with temporary_directory("pyflowmap-test", parent=tmp_path) as name:
            raise RuntimeError(name)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the body exception should propagate")

    assert list(tmp_path.iterdir()) == []
