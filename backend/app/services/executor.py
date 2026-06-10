import os
import subprocess
import textwrap
import uuid
from pathlib import Path

from app.core.config import settings


EXECUTOR_TIMEOUT = settings.executor_timeout


def _build_script(user_code: str, stl_path: str, png_path: str) -> str:
    return textwrap.dedent(f"""
import cadquery as cq
import sys
import os

# ── User code ────────────────────────────────────────────────────────────────
{user_code}

# ── Validate result ───────────────────────────────────────────────────────────
if 'result' not in dir():
    print("ERROR: code must assign final workplane to a variable named `result`", file=sys.stderr)
    sys.exit(1)

# ── Export STL ────────────────────────────────────────────────────────────────
cq.exporters.export(result, "{stl_path}")
print("STL_OK:{stl_path}")

# ── Render PNG ────────────────────────────────────────────────────────────────
# Strategy 1: OCC direct PNG render — best quality, proper 3D shading
# Requires Xvfb virtual display (set via DISPLAY env var in subprocess call)
try:
    from cadquery.occ_impl.geom import Vector
    from cadquery.vis import show_object
    import tempfile

    # Use CadQuery's built-in offline viewer to render a PNG
    # camera_position looks at the part from a 3/4 isometric angle
    cq.exporters.export(
        result,
        "{png_path}",
        exportType="PNG",
        opt={{
            "width": 800,
            "height": 600,
        }}
    )
    print("PNG_OK:{png_path}")
    sys.exit(0)
except Exception as e1:
    print(f"OCC_RENDER_FAILED:{{e1}}", file=sys.stderr)

# Strategy 2: SVG → PNG via cairosvg
try:
    svg_path = "{png_path}".replace(".png", ".svg")
    cq.exporters.export(result, svg_path, exportType="SVG")

    import cairosvg
    cairosvg.svg2png(
        url=svg_path,
        write_to="{png_path}",
        output_width=800,
        output_height=600,
        background_color="white",
    )
    print("PNG_OK:{png_path}")
    sys.exit(0)
except Exception as e2:
    print(f"CAIRO_RENDER_FAILED:{{e2}}", file=sys.stderr)

# Strategy 3: SVG fallback — flat technical drawing, always works
try:
    svg_path = "{png_path}".replace(".png", ".svg")
    cq.exporters.export(result, svg_path, exportType="SVG")
    print("SVG_OK:" + svg_path)
except Exception as e3:
    print(f"RENDER_WARN:{{e3}}", file=sys.stderr)
    print("PNG_SKIP")
""")


class ExecutionResult:
    def __init__(self, success: bool, stl_path: str | None, png_path: str | None,
                 stdout: str, stderr: str):
        self.success = success
        self.stl_path = stl_path
        self.png_path = png_path
        self.stdout = stdout
        self.stderr = stderr


def execute_cadquery(code: str, session_id: str) -> ExecutionResult:
    session_dir = Path(settings.workspace_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())[:8]
    stl_path = str(session_dir / f"model_{run_id}.stl")
    png_path = str(session_dir / f"render_{run_id}.png")
    script_path = session_dir / f"script_{run_id}.py"

    script = _build_script(code, stl_path, png_path)
    script_path.write_text(script)

    try:
        proc = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=EXECUTOR_TIMEOUT,
            env={**os.environ, "DISPLAY": ":99"},
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stl_path=None,
            png_path=None,
            stdout="",
            stderr=f"Execution timed out after {EXECUTOR_TIMEOUT}s",
        )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0 or "STL_OK" not in stdout:
        return ExecutionResult(
            success=False,
            stl_path=None,
            png_path=None,
            stdout=stdout,
            stderr=stderr or "Unknown execution error",
        )

    actual_png = None
    if "PNG_OK" in stdout:
        actual_png = png_path
    elif "SVG_OK" in stdout:
        for line in stdout.splitlines():
            if line.startswith("SVG_OK:"):
                actual_png = line.split("SVG_OK:")[1]
                break

    return ExecutionResult(
        success=True,
        stl_path=stl_path,
        png_path=actual_png,
        stdout=stdout,
        stderr=stderr,
    )