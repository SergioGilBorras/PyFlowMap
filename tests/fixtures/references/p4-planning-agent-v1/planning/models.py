"""Minimal local types; no integration with a real planning system."""
from dataclasses import dataclass, field

@dataclass
class PlanningRequest:
    summary: str = "Synthetic example"
    description: str = "Generated for tests"

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("expected a mapping")
        return cls(summary=str(value.get("summary", "")),
                   description=str(value.get("description", "")))

@dataclass
class PlanningResult:
    status: str
    reuse_analysis: dict = field(default_factory=dict)
    execution_plan: dict = field(default_factory=dict)

    def to_dict(self):
        return {"status": self.status, "reuse_analysis": self.reuse_analysis,
                "execution_plan": self.execution_plan}
