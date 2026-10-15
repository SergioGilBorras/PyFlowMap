# Windows hosted runner: final temporary cleanup limitation

On GitHub-hosted Windows sandboxes, portable-tempdirs may fail to remove the shared pytest workspace at session shutdown with OS error 5 and `TemporaryDirectoryError.code == "CLEANUP_INCOMPLETE"`. This can happen **after every test assertion passes**. The error is preserved in portable-tempdirs diagnostics; it must not be mistaken for evidence that workspace deletion succeeded.

The Windows CI unit-test step explicitly sets `PYFLOWMAP_CI_SKIP_TEMP_CLEANUP=1`. The root pytest `conftest.py` accepts this narrowly scoped **skip of final teardown verification** only when all conditions are true: Windows, `GITHUB_ACTIONS=true`, the explicit opt-in variable, and exactly `CLEANUP_INCOMPLETE`. It emits a visible `PytestWarning` containing `SKIP`. No test itself is skipped, no original cleanup error is silently ignored, and no other exception or platform is exempt. Tests for normal managed-directory cleanup remain enabled.

The default for local Windows, macOS, Linux and non-opted-in environments remains strict: any cleanup error fails the test session. This is only a CI isolation-environment workaround, **not** a change to PyFlowMap's production temporary-directory security, ZIP extraction handling, or the portable-tempdirs dependency.

If the hosted-runner diagnostic reflects a real data exposure, persistent protected directory, or failure outside this precise sandbox case, remove the opt-in and investigate. The warning must be retained in logs and this exception reviewed before release.
