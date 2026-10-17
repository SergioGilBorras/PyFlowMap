"""Invented workflow to exercise conservative static activity analysis."""
from .models import PlanningResult
from .requirement_agent import RequirementAnalysisAgent
from .reuse_research_agent import ReuseResearchAgent
from .decomposition_agent import DecompositionAgent
from .technical_planning_agent import TechnicalPlanningAgent

class PlanningCoordinator:
    def __init__(self):
        self.requirement_agent = RequirementAnalysisAgent()
        self.reuse_agent = ReuseResearchAgent()
        self.decomposition_agent = DecompositionAgent()
        self.technical_agent = TechnicalPlanningAgent()

    def plan(self, request):
        req = self.requirement_agent.analyze(request)
        if req["status"] == "NEEDS_CLARIFICATION":
            return PlanningResult(status="NEEDS_CLARIFICATION")
        reuse = self.reuse_agent.research(request, req["requirements"])
        pieces = self.decomposition_agent.decompose(request, req["requirements"])
        instructions = self.technical_agent.plan(request, req["requirements"], pieces)
        return PlanningResult(status="READY", reuse_analysis=reuse, execution_plan=instructions)
