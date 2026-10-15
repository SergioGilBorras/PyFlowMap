class RequirementAnalysisAgent:
    def analyze(self, request):
        text = (request.summary + " " + request.description).lower()
        unclear = len(request.description.strip()) < 12 or any(x in text for x in ("tbd", "todo", "???", "unclear"))
        return {"status": "NEEDS_CLARIFICATION" if unclear else "READY",
                "clarity": {"is_clear": not unclear, "questions": ["Clarify expected behavior and constraints."] if unclear else []},
                "requirements": [request.summary],
                "acceptance_criteria": [] if unclear else ["Requested behavior is implemented.", "Validation demonstrates expected behavior."]}
