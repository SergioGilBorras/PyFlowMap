from dataclasses import asdict, dataclass, field
from typing import Any

STATUSES = {"READY", "NEEDS_CLARIFICATION", "BLOCKED", "FAILED"}
ACTIONS = {"CREATE_SUBTASK", "CREATE_TASK", "UPDATE_DESCRIPTION", "ADD_RELATION", "MARK_READY_FOR_EXECUTION", "REQUEST_CLARIFICATION"}

@dataclass
class PlanningRequest:
    issue_key: str
    summary: str
    description: str
    priority: str
    issue_origin: str
    project_context: dict[str, Any] | None = None
    workspace: str | None = None

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("request must be an object")
        keys = ("issue_key", "summary", "description", "priority", "issue_origin")
        missing = [k for k in keys if k not in data]
        if missing:
            raise ValueError("missing required fields: " + ", ".join(missing))
        for k in keys:
            if not isinstance(data[k], str) or not data[k].strip():
                raise ValueError(k + " must be a non-empty string")
        if data.get("project_context") is not None and not isinstance(data["project_context"], dict):
            raise ValueError("project_context must be an object or null")
        if data.get("workspace") is not None and not isinstance(data["workspace"], str):
            raise ValueError("workspace must be a string or null")
        return cls(**{k: data.get(k) for k in (*keys, "project_context", "workspace")})

    def to_dict(self):
        return asdict(self)

@dataclass
class PlanningResult:
    status: str
    clarity: dict = field(default_factory=dict)
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    reuse_analysis: dict = field(default_factory=dict)
    decomposition: dict = field(default_factory=dict)
    execution_plan: dict = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    jira_actions: list[dict] = field(default_factory=list)
    summary: str = ""
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError("invalid status")
        if any(a.get("type") not in ACTIONS for a in self.jira_actions):
            raise ValueError("invalid Jira action")
    def to_dict(self):
        return asdict(self)
