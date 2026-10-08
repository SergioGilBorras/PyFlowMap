"""Optional image rendering through the separately installed Mermaid CLI (mmdc)."""

from pathlib import Path
import shutil
import subprocess


class RenderError(RuntimeError):
    pass


def render(mmd: Path, dest: Path) -> Path:
    if dest.suffix.lower() not in (".svg", ".png"):
        raise ValueError("Render destination must have .svg or .png extension")
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
    return dest
