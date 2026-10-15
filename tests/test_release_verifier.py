"""Offline installer status may never hide a failed console launcher."""

import pytest

from scripts.verify_offline_release_install import _status_for_summary


@pytest.mark.parametrize(
    ("verified", "launcher", "expected"),
    [
        (True, "PASS", "PASS"),
        (True, "BLOCKED", "PARTIAL"),
        (True, "FAIL", "FAIL"),
        (True, "NOT_RUN", "FAIL"),
        (False, "PASS", "FAIL"),
        (False, "BLOCKED", "FAIL"),
    ],
)
def test_offline_verifier_reports_launcher_status(verified, launcher, expected):
    assert _status_for_summary(verified, launcher) == expected
