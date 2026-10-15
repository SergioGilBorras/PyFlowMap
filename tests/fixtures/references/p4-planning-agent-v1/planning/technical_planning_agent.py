class TechnicalPlanningAgent:
    def plan(self, request, requirements, decomposition):
        return {"implementation_steps": decomposition["internal_steps"] or [t["title"] for t in decomposition["subtasks"]],
                "components_affected": list((request.project_context or {}).get("components", [])),
                "validation_strategy": ["Add or update focused unit tests", "Run full test suite"],
                "risks": ["Project details may require clarification."],
                "definition_of_done": ["Acceptance criteria met", "Tests pass", "Proposal reviewed"]}
