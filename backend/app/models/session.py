from typing import Literal

from app.models.orm import CADModel, Message, Session


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


async def update_session_pending(
    session: Session,
    pending_code: str | None = None,
    pending_plan: str | None = None,
) -> None:
    session.pending_code = pending_code
    session.pending_plan = pending_plan
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