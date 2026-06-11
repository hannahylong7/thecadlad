from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.models.orm import Session
from app.models.schemas import (
    ApproveRequest,
    MessageRequest,
    MessageResponse,
    ModelResponse,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    AgentResponse,
    JobResponse,
)
from app.models.session import (
    create_session,
    get_cad_models,
    get_messages,
    get_session,
    list_sessions,
    get_jobs,
)
from app.services.agent import (
    approve_geometry,
    handle_code_response,
    handle_plan_response,
    run_agent_turn,
    execute_approved_code
)
from app.models.session import update_session_status

router = APIRouter()


@router.post("/sessions", status_code=201)
async def new_session() -> SessionCreateResponse:
    session = await create_session()
    return SessionCreateResponse(
        id=str(session.id),
        status=session.status,
        created_at=session.created_at,
    )


@router.get("/sessions")
async def get_sessions() -> list[SessionSummaryResponse]:
    sessions = await list_sessions()
    return [
        SessionSummaryResponse(
            id=str(s.id),
            title=s.title,
            status=s.status,
            iteration=s.iteration,
            has_render=s.current_png_path is not None,
            has_model=s.current_stl_path is not None and s.status == "approved",
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str) -> SessionDetailResponse:
    session = await _get_or_404(session_id)
    return await _session_to_detail(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    session = await _get_or_404(session_id)
    await session.delete()


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, body: MessageRequest) -> AgentResponse:
    session = await _get_or_404(session_id)

    if session.status == "executing":
        raise HTTPException(409, "Session is currently executing — please wait")

    result = await run_agent_turn(session, body.content)

    session = await _get_or_404(session_id)
    return {**result, "session_status": session.status}


@router.post("/sessions/{session_id}/approve")
async def approve_step(session_id: str, body: ApproveRequest) -> AgentResponse:
    session = await _get_or_404(session_id)

    if session.status == "awaiting_plan_approval":
        result = await handle_plan_response(session, body.approved, body.feedback)
    elif session.status == "awaiting_code_approval":
        result = await handle_code_response(session, body.approved, body.feedback)
    else:
        raise HTTPException(409, f"Nothing to approve in status: {session.status}")

    session = await _get_or_404(session_id)
    return {**result, "session_status": session.status}


@router.post("/sessions/{session_id}/approve-geometry")
async def approve_geometry_endpoint(session_id: str) -> AgentResponse:
    session = await _get_or_404(session_id)

    if session.status != "rendered":
        raise HTTPException(409, "No rendered geometry to approve")

    result = await approve_geometry(session)
    session = await _get_or_404(session_id)
    return {**result, "session_status": session.status}


@router.get("/sessions/{session_id}/render")
async def get_render(session_id: str):
    session = await _get_or_404(session_id)
    if not session.current_png_path:
        raise HTTPException(404, "No render available")
    return FileResponse(
        session.current_png_path,
        media_type="image/png" if session.current_png_path.endswith(".png") else "image/svg+xml",
    )


@router.get("/sessions/{session_id}/model")
async def get_model(session_id: str):
    session = await _get_or_404(session_id)
    if not session.current_stl_path or session.status != "approved":
        raise HTTPException(404, "No approved model available")
    return FileResponse(session.current_stl_path, media_type="application/octet-stream")


@router.get("/sessions/{session_id}/jobs")
async def get_session_jobs(session_id: str) -> list[JobResponse]:
    session = await _get_or_404(session_id)
    jobs = await get_jobs(session)
    return [
        JobResponse(
            id=str(j.id),
            session_id=str(session.id),
            status=j.status,
            iteration=j.iteration,
            duration_ms=j.duration_ms,
            stl_path=j.stl_path,
            png_path=j.png_path,
            created_at=j.created_at,
        )
        for j in jobs
    ]
 
 
@router.post("/sessions/{session_id}/approve/async")
async def approve_step_async(
    session_id: str,
    body: ApproveRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    session = await _get_or_404(session_id)
 
    if session.status == "awaiting_plan_approval":
        result = await handle_plan_response(session, body.approved, body.feedback)
        session = await _get_or_404(session_id)
        return {**result, "session_status": session.status}
 
    elif session.status == "awaiting_code_approval":
        if not body.approved:
            result = await handle_code_response(session, False, body.feedback)
            session = await _get_or_404(session_id)
            return {**result, "session_status": session.status}
 
        # Kick off execution as background task, return immediately
        background_tasks.add_task(_run_execution_background, session_id)
        await update_session_status(session, "executing")
        return {
            "type": "executing",
            "session_status": "executing",
        }
 
    else:
        raise HTTPException(409, f"Nothing to approve in status: {session.status}")
 
 
async def _run_execution_background(session_id: str) -> None:
    try:
        session = await get_session(session_id)
        if session:
            await execute_approved_code(session)
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("background execution crashed session=%s error=%s", session_id, exc)
        try:
            session = await get_session(session_id)
            if session:
                await update_session_status(session, "error")
        except Exception:
            pass


async def _get_or_404(session_id: str) -> Session:
    session = await get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


async def _session_to_detail(session: Session) -> SessionDetailResponse:
    messages = await get_messages(session)
    models = await get_cad_models(session)

    return SessionDetailResponse(
        id=str(session.id),
        title=session.title,
        status=session.status,
        messages=[
            MessageResponse(
                role=m.role,
                content=m.content,
                code=m.code,
                plan=m.plan,
                timestamp=m.created_at,
            )
            for m in messages
        ],
        iteration=session.iteration,
        has_render=session.current_png_path is not None,
        has_model=session.current_stl_path is not None and session.status == "approved",
        version_count=len(models),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )