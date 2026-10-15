"""Synthetic console adapter used only as static-analysis fixture."""
import json
import sys
from planning.coordinator import PlanningCoordinator
from planning.models import PlanningRequest

def main():
    try:
        source = json.load(sys.stdin)
        request = PlanningRequest.from_dict(source)
        coordinator = PlanningCoordinator()
        result = coordinator.plan(request)
        sys.stdout.write(json.dumps(result.to_dict()) + "\n")
        return 0
    except (ValueError, json.JSONDecodeError):
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
