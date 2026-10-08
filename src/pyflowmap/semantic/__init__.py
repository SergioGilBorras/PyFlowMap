"""Optional, user-supplied semantic labeling; no AI dependency is bundled."""

from .contracts import LabelRequest, SemanticLabelProvider
from .enrich import enrich_activity_labels

__all__ = ["LabelRequest", "SemanticLabelProvider", "enrich_activity_labels"]
