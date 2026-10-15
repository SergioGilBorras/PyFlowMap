"""Synthetic console entry for static call-resolution tests."""
import json
import sys
from planning.coordinator import PlanningCoordinator
from planning.models import PlanningRequest

def main():
    try:
        payload = json.load(sys.stdin)
        request = PlanningRequest.from_dict(payload)
        # The next call intentionally occurs on line 12.
        payload.setdefault("fixture", True)
        result = PlanningCoordinator().plan(request)
        sys.stdout.write(json.dumps(result.to_dict()) + "\n")
        return 0
    except (ValueError, json.JSONDecodeError):
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
