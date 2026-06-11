import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from app.core.config import settings
from app.models.orm import Session
from app.models.session import (
    MAX_ITERATIONS,
    add_message,
    approve_cad_model,
    clear_pending_plan,
    clear_pending_state,
    create_cad_model,
    set_session_title,
    set_pending_code,
    set_pending_plan,
    to_openai_messages,
    update_session_artifact,
    update_session_status,
    complete_job,
    create_job,
    fail_job,
)
from app.services.executor import execute_cadquery
from app.services.tools.definitions import SYSTEM_PROMPT, TOOLS

import logging
import time

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)
ToolFunction = Callable[..., Awaitable[dict[str, Any]]]


async def _tool_propose_plan(
    session: Session,
    plan: str,
    assumptions: list[str],
) -> dict[str, Any]:
    await set_pending_plan(session, plan)
    await update_session_status(session, "awaiting_plan_approval")
    return {
        "type": "plan_proposal",
        "plan": plan,
        "assumptions": assumptions,
    }


async def _tool_propose_cadquery_code(
    session: Session,
    code: str,
    description: str,
) -> dict[str, Any]:
    await set_pending_code(session, code)
    await update_session_status(session, "awaiting_code_approval")
    return {
        "type": "code_proposal",
        "code": code,
        "description": description,
    }


async def _tool_self_correct(
    session: Session,
    error_analysis: str,
    corrected_code: str,
) -> dict[str, Any]:
    await set_pending_code(session, corrected_code)
    await update_session_status(session, "awaiting_code_approval")
    return {
        "type": "self_correction",
        "error_analysis": error_analysis,
        "code": corrected_code,
    }


TOOL_FUNCTIONS: dict[str, ToolFunction] = {
    "propose_plan": _tool_propose_plan,
    "propose_cadquery_code": _tool_propose_cadquery_code,
    "self_correct": _tool_self_correct,
}


def _validate_tool_registry() -> None:
    schema_tool_names = {tool["function"]["name"] for tool in TOOLS}
    callable_tool_names = set(TOOL_FUNCTIONS)

    missing_callables = schema_tool_names - callable_tool_names
    missing_schemas = callable_tool_names - schema_tool_names

    if missing_callables or missing_schemas:
        details = []
        if missing_callables:
            details.append(f"missing callables: {sorted(missing_callables)}")
        if missing_schemas:
            details.append(f"missing schemas: {sorted(missing_schemas)}")
        raise RuntimeError(f"Tool registry mismatch ({'; '.join(details)})")


_validate_tool_registry()


async def _create_chat_completion(
    messages: list[dict[str, Any]],
    tool_choice: Any,
) -> Any:
    return await client.chat.completions.create(
        model=settings.model,
        messages=cast(list[ChatCompletionMessageParam], messages),
        tools=cast(list[ChatCompletionToolParam], TOOLS),
        tool_choice=tool_choice,
        parallel_tool_calls=False,
    )


async def _run_tool_call(session: Session, tool_call: Any) -> dict[str, Any]:
    fn_name = tool_call.function.name
    function_to_call = TOOL_FUNCTIONS.get(fn_name)
    if function_to_call is None:
        logger.warning("unknown tool call session=%s tool=%s", session.id, fn_name)
        await update_session_status(session, "idle")
        return {
            "type": "error",
            "content": f"Unknown tool requested by model: {fn_name}",
        }

    try:
        fn_args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError as exc:
        logger.warning(
            "invalid tool arguments session=%s tool=%s error=%s",
            session.id,
            fn_name,
            exc,
        )
        await update_session_status(session, "idle")
        return {
            "type": "error",
            "content": f"Invalid arguments for tool {fn_name}",
        }

    await add_message(
        session,
        "assistant",
        content=f"[tool_call: {fn_name}]",
        code=fn_args.get("code") or fn_args.get("corrected_code"),
        plan=fn_args.get("plan"),
    )

    try:
        return await function_to_call(session=session, **fn_args)
    except TypeError as exc:
        logger.warning(
            "tool argument mismatch session=%s tool=%s args=%s error=%s",
            session.id,
            fn_name,
            sorted(fn_args),
            exc,
        )
        await update_session_status(session, "idle")
        return {
            "type": "error",
            "content": f"Invalid arguments for tool {fn_name}",
        }


async def run_agent_turn(
    session: Session,
    user_message: str,
    force_tool: str | None = None,
) -> dict:

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

    nudged_for_tool = False
    while True:
        response = await _create_chat_completion(messages, tool_choice)
        choice = response.choices[0]

        tool_calls = choice.message.tool_calls or []
        fn_name = tool_calls[0].function.name if tool_calls else "none"
        logger.info("agent_turn session=%s model=%s tool=%s status=%s", session.id, settings.model, fn_name, session.status)

        if tool_calls:
            tool_call = tool_calls[0]
            return await _run_tool_call(session, tool_call)

        text = choice.message.content or ""

        if session.status not in ("planning", "coding") or nudged_for_tool:
            break

        await add_message(session, "assistant", text)
        nudge = "Please now call the propose_cadquery_code tool to write the actual code."
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": nudge})
        nudged_for_tool = True

    await add_message(session, "assistant", text)
    await update_session_status(session, "idle")
    return {"type": "message", "content": text}


async def execute_approved_code(session: Session) -> dict[str, Any]:

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
        if not result.stl_path:
            error = "Execution reported success without an STL artifact."
            await fail_job(job, error, duration_ms)
            await update_session_status(session, "error")
            return {"type": "error", "content": error}

        await complete_job(job, result.stl_path, result.png_path, result.stdout or "", duration_ms)

        await update_session_artifact(session, result.stl_path, result.png_path)
        await create_cad_model(session, result.stl_path, result.png_path)

        await clear_pending_state(session)
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
        await clear_pending_plan(session)
        return await run_agent_turn(
            session,
            "Plan approved. Please write the CadQuery code.",
            force_tool="propose_cadquery_code",
        )
    else:
        await clear_pending_state(session)
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
        await clear_pending_state(session)
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
