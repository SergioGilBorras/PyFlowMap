"""A final pure stage for cross-file resolution."""
class TechnicalPlanningAgent:
    def plan(self, request, requirements, decomposition):
        return {"steps": decomposition["steps"], "ready": bool(requirements)}
