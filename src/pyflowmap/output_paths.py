"""Create dated destinations for end-user diagrams, separate from validation."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4


def next_graph_directory(parent: Path) -> Path:
    """Supply a unique dated destination. The service creates it on writing."""
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    return parent / f"{stamp}_{uuid4().hex[:8]}"
