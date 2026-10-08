class DecompositionAgent:
    def decompose(self, request, requirements):
        text = (request.summary + " " + request.description).lower()
        split = any(x in text for x in ("independent", "separately", "multiple components", "and then"))
        if split:
            tasks = [{"title": "Implement core change", "depends_on": []}, {"title": "Validate integration", "depends_on": ["Implement core change"]}]
            return {"should_split": True, "internal_steps": [], "subtasks": tasks, "independent_tasks": [], "dependencies": [{"from": tasks[0]["title"], "to": tasks[1]["title"]}]}
        return {"should_split": False, "internal_steps": ["Implement requested change", "Validate change"], "subtasks": [], "independent_tasks": [], "dependencies": []}
