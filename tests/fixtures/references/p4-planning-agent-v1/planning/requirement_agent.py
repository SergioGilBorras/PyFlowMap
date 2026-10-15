"""Synthetic first stage; contains no external project logic."""
class RequirementAnalysisAgent:
    def analyze(self, request):
        if len(request.description.strip()) < 8:
            return {"status": "NEEDS_CLARIFICATION", "requirements": []}
        return {"status": "READY", "requirements": [request.summary]}
