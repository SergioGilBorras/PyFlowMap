"""Optional image rendering through the separately installed Mermaid CLI (mmdc)."""

import shutil
import subprocess
from pathlib import Path

from .dot import to_dot
from .models import FlowGraph


class RenderError(RuntimeError):
    pass


def render(mmd: Path, dest: Path, graph: FlowGraph | None = None,
           renderer: str = "auto", direction: str = "TD") -> tuple[Path, str]:
    if dest.suffix.lower() not in (".svg", ".png"):
        raise ValueError("Render destination must have .svg or .png extension")
    if renderer not in ("auto", "mermaid", "graphviz"):
        raise ValueError("renderer must be auto, mermaid or graphviz")
    if renderer == "auto":
        renderer = "mermaid" if shutil.which("mmdc") else "graphviz"
    if renderer == "graphviz":
        executable = shutil.which("dot")
        if not executable or graph is None:
            raise RenderError(
                "Image export requires Mermaid CLI (`npm install -g @mermaid-js/mermaid-cli`) "
                "or Graphviz (`dot` on PATH)."
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run([executable, f"-T{dest.suffix[1:]}", "-o", str(dest)],
                                    input=to_dot(graph, direction), capture_output=True,
                                    text=True, timeout=90, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RenderError(f"Graphviz failed to run: {exc}") from exc
        if result.returncode != 0 or not dest.is_file():
            raise RenderError(f"Graphviz failed: {(result.stderr or result.stdout)[-800:]}")
        return dest, "graphviz"
    executable = shutil.which("mmdc")
    if not executable:
        raise RenderError(
            "Image export requires Mermaid CLI. Install with `npm install -g @mermaid-js/mermaid-cli`. "
            "The .mmd file can still be used without Node.js."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run([executable, "-i", str(mmd), "-o", str(dest)],
                                capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(f"Mermaid CLI failed to run: {exc}") from exc
    if result.returncode != 0 or not dest.is_file():
        raise RenderError(f"Mermaid CLI failed: {(result.stderr or result.stdout)[-800:]}")
    return dest, "mermaid"
