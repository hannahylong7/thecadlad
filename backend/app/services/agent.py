import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.orm import Session
from app.models.session import (
    MAX_ITERATIONS,
    MessageRole,
    add_message,
    approve_cad_model,
    create_cad_model,
    set_session_title,
    to_openai_messages,
    update_session_artifact,
    update_session_pending,
    update_session_status,
    complete_job,
    create_job,
    fail_job,
)
from app.services.executor import execute_cadquery
from app.services.tools.definitions import SYSTEM_PROMPT, TOOLS

import re

import logging
import time

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)


def _extract_code_block(text: str) -> str | None:
    match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Only treat as CadQuery code if it looks like it
        if 'cq.' in code or 'result' in code:
            return code
    return None


async def run_agent_turn(session: Session, user_message: str, force_tool: str | None = None) -> dict:

    await add_message(session, "user", user_message)
    await update_session_status(session, "planning")

    if session.title == "Untitled session":
        await set_session_title(session, user_message)

    history = await to_openai_messages(session)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    tool_choice = (
        {"type": "function", "function": {"name": force_tool}}
        if force_tool else "auto"
    )
    response = await client.chat.completions.create(
        model=settings.model,
        messages=messages,
        tools=TOOLS,
        tool_choice=tool_choice,
    )

    choice = response.choices[0]

    fn_name = choice.message.tool_calls[0].function.name if choice.finish_reason == "tool_calls" else "none"
    logger.info("agent_turn session=%s model=%s tool=%s status=%s", session.id, settings.model, fn_name, session.status)

    if choice.finish_reason == "tool_calls":
        tool_call = choice.message.tool_calls[0]
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)

        await add_message(
            session,
            "assistant",
            content=f"[tool_call: {fn_name}]",
            code=fn_args.get("code") or fn_args.get("corrected_code"),
            plan=fn_args.get("plan"),
        )

        if fn_name == "propose_plan":
            await update_session_pending(session, pending_plan=fn_args["plan"])
            await update_session_status(session, "awaiting_plan_approval")
            return {
                "type": "plan_proposal",
                "plan": fn_args["plan"],
                "assumptions": fn_args.get("assumptions", []),
            }

        elif fn_name == "propose_cadquery_code":
            await update_session_pending(session, pending_code=fn_args["code"])
            await update_session_status(session, "awaiting_code_approval")
            return {
                "type": "code_proposal",
                "code": fn_args["code"],
                "description": fn_args.get("description", ""),
            }

        elif fn_name == "self_correct":
            await update_session_pending(session, pending_code=fn_args["corrected_code"])
            await update_session_status(session, "awaiting_code_approval")
            return {
                "type": "self_correction",
                "error_analysis": fn_args["error_analysis"],
                "code": fn_args["corrected_code"],
            }


    text = choice.message.content or ""

    extracted = _extract_code_block(text)
    if extracted:
        await add_message(session, "assistant", content="[tool_call: propose_cadquery_code]", code=extracted)
        await update_session_pending(session, pending_code=extracted)
        await update_session_status(session, "awaiting_code_approval")
        return {
            "type": "code_proposal",
            "code": extracted,
            "description": "Code extracted from agent response",
        }

    if session.status in ("planning", "coding"):
        await add_message(session, "assistant", text)
        nudge = "Please now call the propose_cadquery_code tool to write the actual code."
        return await run_agent_turn(session, nudge)

    await add_message(session, "assistant", text)
    await update_session_status(session, "idle")
    return {"type": "message", "content": text}


async def execute_approved_code(session: Session) -> dict:

    if session.iteration >= MAX_ITERATIONS:
        await update_session_status(session, "error")
        return {
            "type": "error",
            "content": f"Max iterations ({MAX_ITERATIONS}) reached. Please start a new session.",
        }

    if not session.pending_code:
        return {"type": "error", "content": "No pending code to execute"}
    
    job = await create_job(session, session.pending_code)
    await update_session_status(session, "executing")

    start = time.time()
    result = execute_cadquery(session.pending_code, str(session.id))
    duration_ms = int((time.time() - start) * 1000)
    logger.info("execution session=%s iteration=%d success=%s duration_ms=%d", session.id, session.iteration, result.success, duration_ms)

    if result.success:
        await complete_job(job, result.stl_path, result.png_path, result.stdout or "", duration_ms)

        await update_session_artifact(session, result.stl_path, result.png_path)
        await create_cad_model(session, result.stl_path, result.png_path)

        await update_session_pending(session, pending_code=None)
        await update_session_status(session, "rendered")

        await add_message(
            session,
            "assistant",
            "✓ Model rendered successfully. Approve the geometry to load the 3D viewer, or describe changes.",
        )
        return {
            "type": "render_complete",
            "png_path": result.png_path,
            "stl_path": result.stl_path,
            "job_id": str(job.id),
            "duration_ms": duration_ms,
        }

    else:
        timed_out = "timed out" in (result.stderr or "").lower()
        await fail_job(job, result.stderr or "", duration_ms, timed_out=timed_out)
        await update_session_status(session, "error")
        error_msg = f"Execution failed:\n{result.stderr}"

        return await run_agent_turn(session, error_msg)


async def handle_plan_response(
    session: Session,
    approved: bool,
    feedback: str | None,
) -> dict:
    if approved:
        await update_session_pending(session, pending_plan=None)
        return await run_agent_turn(
            session,
            "Plan approved. Please write the CadQuery code.",
            force_tool="propose_cadquery_code",
        )
    else:
        await update_session_pending(session, pending_plan=None)
        await update_session_status(session, "idle")
        feedback_msg = f"Plan rejected. Feedback: {feedback or 'Please revise.'}"
        return await run_agent_turn(session, feedback_msg)


async def handle_code_response(
    session: Session,
    approved: bool,
    feedback: str | None,
) -> dict:
    if approved:
        return await execute_approved_code(session)
    else:
        await update_session_pending(session, pending_code=None)
        await update_session_status(session, "idle")
        feedback_msg = f"Code rejected. Feedback: {feedback or 'Please revise.'}"
        return await run_agent_turn(session, feedback_msg)


async def approve_geometry(session: Session) -> dict:
    await update_session_status(session, "approved")
    await approve_cad_model(session)
    await add_message(session, "assistant", "✓ Geometry approved. 3D viewer is ready.")
    return {
        "type": "geometry_approved",
        "stl_path": session.current_stl_path,
    }