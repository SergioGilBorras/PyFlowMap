"""Deterministic in-memory fixture stage."""
class DecompositionAgent:
    def decompose(self, request, requirements):
        return {"steps": ["inspect", "build", "verify"], "count": len(requirements)}
