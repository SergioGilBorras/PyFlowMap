import json
import logging
import sys
from planning.coordinator import PlanningCoordinator
from planning.models import PlanningRequest

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s: %(message)s")

def main():
    try:
        request = PlanningRequest.from_dict(json.load(sys.stdin))
        result = PlanningCoordinator().plan(request)
        sys.stdout.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        return 0
    except (ValueError, json.JSONDecodeError) as exc:
        logging.error("Invalid request: %s", exc)
        return 1
    except Exception:
        logging.exception("Planning failed")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
