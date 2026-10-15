from .models import PlanningResult
from .requirement_agent import RequirementAnalysisAgent
from .reuse_research_agent import ReuseResearchAgent
from .decomposition_agent import DecompositionAgent
from .technical_planning_agent import TechnicalPlanningAgent

class PlanningCoordinator:
    def __init__(self, requirement_agent=None, reuse_agent=None, decomposition_agent=None, technical_agent=None):
        self.requirement_agent = requirement_agent or RequirementAnalysisAgent()
        self.reuse_agent = reuse_agent or ReuseResearchAgent()
        self.decomposition_agent = decomposition_agent or DecompositionAgent()
        self.technical_agent = technical_agent or TechnicalPlanningAgent()

    def plan(self, request):
        req = self.requirement_agent.analyze(request)
        if req["status"] == "NEEDS_CLARIFICATION":
            return PlanningResult(status=req["status"], clarity=req["clarity"], requirements=req["requirements"],
                summary="Clarification required.", jira_actions=[{"type": "REQUEST_CLARIFICATION", "questions": req["clarity"]["questions"]}])
        reuse = self.reuse_agent.research(request, req["requirements"])
        dec = self.decomposition_agent.decompose(request, req["requirements"])
        tech = self.technical_agent.plan(request, req["requirements"], dec)
        actions = [{"type":"CREATE_SUBTASK","title":t["title"],"depends_on":t["depends_on"]} for t in dec["subtasks"]]
        actions += [{"type":"CREATE_TASK","title":t["title"]} for t in dec["independent_tasks"]]
        actions += [{"type":"UPDATE_DESCRIPTION","proposed_description":tech["implementation_steps"]},{"type":"MARK_READY_FOR_EXECUTION"}]
        return PlanningResult(status="READY", clarity=req["clarity"], requirements=req["requirements"],
            acceptance_criteria=req["acceptance_criteria"], reuse_analysis=reuse, decomposition=dec,
            execution_plan=tech, risks=tech["risks"], jira_actions=actions, summary="Planning completed.")
