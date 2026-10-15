class ReuseResearchAgent:
    def research(self, request, requirements):
        return {"mode": "mock", "recommendation": "ASSESS_EXISTING_CAPABILITIES_BEFORE_BUILD", "candidates": [],
                "considerations": {"libraries": [], "frameworks": [], "oss": [], "license": "review before adoption",
                "maintenance": "assess support", "security": "review advisories", "compatibility": "verify constraints"},
                "rationale": "No external research is performed."}
