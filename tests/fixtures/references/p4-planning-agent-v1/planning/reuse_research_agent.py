"""Mock-only stage; never contacts a network service."""
class ReuseResearchAgent:
    def research(self, request, requirements):
        return {"source": "synthetic", "items": list(requirements)}
