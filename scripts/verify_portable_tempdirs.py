"""Fail setup unless the explicitly pinned portable-tempdirs commit is active."""

import json
from importlib.metadata import distribution


EXPECTED_COMMIT = "fd6dbd640630e6911a53b4d756089099ec870a8b"
EXPECTED_VERSION = "0.1.2"


def main() -> int:
    package = distribution("portable-tempdirs")
    direct_url = json.loads(package.read_text("direct_url.json") or "{}")
    commit = direct_url.get("vcs_info", {}).get("commit_id")
    if package.version != EXPECTED_VERSION or commit != EXPECTED_COMMIT:
        raise SystemExit(
            "portable-tempdirs must be version 0.1.2 from commit "
            f"{EXPECTED_COMMIT}; found version={package.version}, commit={commit}"
        )
    print(f"portable-tempdirs {package.version} @ {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
