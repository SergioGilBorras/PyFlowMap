"""Real-provider runner must record timeouts and continue to later cases."""

import json
import runpy
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_real_runner_records_provider_timeout_and_continues(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    runner = runpy.run_path(str(ROOT / "scripts" / "compare_real_labeler.py"))
    main = runner["main"]
    cases = [{"id": "first", "suite": "baseline"},
             {"id": "second", "suite": "baseline"}]
    processed = []

    def simulated_case(case, root, timeout):
        processed.append(case["id"])
        if case["id"] == "first":
            raise RuntimeError("codex analysis returned 2: "
                               "P4 semantic labeling failed (ProviderTimeout)")
        return ({"case": case["id"], "suite": "baseline",
                 "status": "PASS", "semantic_fidelity": "REVIEW"}, [])

    monkeypatch.setitem(main.__globals__, "all_cases", lambda: cases)
    monkeypatch.setitem(main.__globals__, "run_case", simulated_case)
    monkeypatch.setattr("shutil.which", lambda name: "available")
    for package in ("p4_codex_bridge", "p4_semantic_labeler"):
        monkeypatch.setitem(sys.modules, package, types.ModuleType(package))

    code = main([
        "--acknowledge-source-transmission",
        "--output", str(tmp_path / "real-results"),
    ])
    report = json.loads(
        (tmp_path / "real-results" / "real-labeler-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert code == 1
    assert processed == ["first", "second"]
    assert report["cases_completed"] == 2
    assert report["cases"][0]["failure_type"] == "PROVIDER_TIMEOUT"
    assert report["cases"][1]["status"] == "PASS"
    assert all(isinstance(row["elapsed_seconds"], float)
               for row in report["cases"])
