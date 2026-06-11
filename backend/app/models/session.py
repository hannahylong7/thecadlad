from typing import Literal

from app.models.orm import CADModel, Message, Session, CADJob


MessageRole = Literal["user", "assistant", "system"]
SessionStatus = Literal[
    "idle",
    "planning",
    "awaiting_plan_approval",
    "coding",
    "awaiting_code_approval",
    "executing",
    "rendered",
    "approved",
    "error",
]

MAX_ITERATIONS = 10


async def create_session() -> Session:
    return await Session.create(status="idle")


async def get_session(session_id: str) -> Session | None:
    return await Session.get_or_none(id=session_id)


async def list_sessions() -> list[Session]:
    return await Session.all()


async def update_session_status(session: Session, status: SessionStatus) -> None:
    session.status = status
    await session.save(update_fields=["status", "updated_at"])


async def set_pending_plan(session: Session, plan: str) -> None:
    session.pending_plan = plan
    await session.save(update_fields=["pending_plan", "updated_at"])


async def clear_pending_plan(session: Session) -> None:
    session.pending_plan = None
    await session.save(update_fields=["pending_plan", "updated_at"])


async def set_pending_code(session: Session, code: str) -> None:
    session.pending_code = code
    await session.save(update_fields=["pending_code", "updated_at"])


async def clear_pending_code(session: Session) -> None:
    session.pending_code = None
    await session.save(update_fields=["pending_code", "updated_at"])


async def clear_pending_state(session: Session) -> None:
    session.pending_code = None
    session.pending_plan = None
    await session.save(update_fields=["pending_code", "pending_plan", "updated_at"])


async def update_session_artifact(
    session: Session,
    stl_path: str,
    png_path: str | None,
) -> None:
    session.current_stl_path = stl_path
    session.current_png_path = png_path
    session.iteration += 1
    await session.save(update_fields=[
        "current_stl_path",
        "current_png_path",
        "iteration",
        "updated_at",
    ])


async def set_session_title(session: Session, title: str) -> None:
    session.title = title[:255]
    await session.save(update_fields=["title", "updated_at"])


async def add_message(
    session: Session,
    role: MessageRole,
    content: str,
    code: str | None = None,
    plan: str | None = None,
) -> Message:
    return await Message.create(
        session=session,
        role=role,
        content=content,
        code=code,
        plan=plan,
    )


async def get_messages(session: Session) -> list[Message]:
    return await Message.filter(session=session).order_by("created_at")


async def to_openai_messages(session: Session) -> list[dict]:
    messages = await get_messages(session)
    return [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in ("user", "assistant", "system")
    ]


async def create_cad_model(
    session: Session,
    stl_path: str,
    png_path: str | None,
) -> CADModel:
    return await CADModel.create(
        session=session,
        stl_path=stl_path,
        png_path=png_path,
        iteration=session.iteration,
    )


async def get_cad_models(session: Session) -> list[CADModel]:
    return await CADModel.filter(session=session).order_by("-created_at")


async def approve_cad_model(session: Session) -> CADModel | None:
    model = await CADModel.filter(session=session).order_by("-created_at").first()
    if model:
        model.approved = True
        await model.save(update_fields=["approved"])
    return model


async def create_job(session: Session, code: str) -> CADJob:
    """Create a new job record before execution starts."""
    return await CADJob.create(
        session=session,
        code=code,
        status="pending",
        iteration=session.iteration + 1,
    )
 
 
async def complete_job(
    job: CADJob,
    stl_path: str,
    png_path: str | None,
    stdout: str,
    duration_ms: int,
) -> None:
    """Mark a job as complete with artifact paths and timing."""
    job.status = "complete"
    job.stl_path = stl_path
    job.png_path = png_path
    job.stdout = stdout
    job.duration_ms = duration_ms
    await job.save(update_fields=["status", "stl_path", "png_path", "stdout", "duration_ms", "updated_at"])
 
 
async def fail_job(job: CADJob, stderr: str, duration_ms: int, timed_out: bool = False) -> None:
    """Mark a job as failed with error output."""
    job.status = "timeout" if timed_out else "failed"
    job.stderr = stderr
    job.duration_ms = duration_ms
    await job.save(update_fields=["status", "stderr", "duration_ms", "updated_at"])
 
 
async def get_jobs(session: Session) -> list[CADJob]:
    """All jobs for a session, newest first."""
    return await CADJob.filter(session=session).order_by("-created_at")