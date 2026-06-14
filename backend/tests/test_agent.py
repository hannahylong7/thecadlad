import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tortoise import Tortoise

from app.services.agent import run_agent_turn, execute_approved_code
from app.models.session import (
    MAX_ITERATIONS,
    clear_pending_state,
    create_session,
    get_messages,
    set_pending_code,
    set_pending_plan,
    add_message,
    to_openai_messages,
)
from app.models.orm import Session


# Test database setup

@pytest.fixture()
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.orm"]},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_run_agent_turn_plan_proposal(db):
    """
    When OpenAI returns a propose_plan tool call, run_agent_turn should:
    1. Return {"type": "plan_proposal", ...}
    2. Transition session status to "awaiting_plan_approval"
    3. Persist pending_plan to the database
    """
    session = await create_session()

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_plan"
    mock_tool_call.function.arguments = json.dumps({
        "plan": "Create a 50x30x10mm box with four M3 holes at corners.",
        "assumptions": ["Wall thickness 2mm", "Hole inset 8mm"],
    })

    mock_choice = MagicMock()
    mock_choice.finish_reason = "tool_calls"
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Make me a mounting bracket")

    assert result["type"] == "plan_proposal"
    assert "50x30x10mm" in result["plan"]
    assert len(result["assumptions"]) == 2

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "awaiting_plan_approval"
    assert refreshed.pending_plan is not None
    assert "50x30x10mm" in refreshed.pending_plan


@pytest.mark.asyncio
async def test_set_pending_plan_does_not_clear_pending_code(db):
    session = await create_session()
    await set_pending_code(session, "result = cq.Workplane('XY').box(1, 1, 1)")

    await set_pending_plan(session, "Make a cube.")

    refreshed = await Session.get(id=session.id)
    assert refreshed.pending_plan == "Make a cube."
    assert refreshed.pending_code == "result = cq.Workplane('XY').box(1, 1, 1)"


@pytest.mark.asyncio
async def test_set_pending_code_does_not_clear_pending_plan(db):
    session = await create_session()
    await set_pending_plan(session, "Make a cube.")

    await set_pending_code(session, "result = cq.Workplane('XY').box(1, 1, 1)")

    refreshed = await Session.get(id=session.id)
    assert refreshed.pending_plan == "Make a cube."
    assert refreshed.pending_code == "result = cq.Workplane('XY').box(1, 1, 1)"


@pytest.mark.asyncio
async def test_clear_pending_state_clears_plan_and_code(db):
    session = await create_session()
    await set_pending_plan(session, "Make a cube.")
    await set_pending_code(session, "result = cq.Workplane('XY').box(1, 1, 1)")

    await clear_pending_state(session)

    refreshed = await Session.get(id=session.id)
    assert refreshed.pending_plan is None
    assert refreshed.pending_code is None


@pytest.mark.asyncio
async def test_to_openai_messages_includes_persisted_plan_and_code(db):
    session = await create_session()

    plan = "Create a 50x30x10mm enclosure with four mounting holes."
    code = "result = cq.Workplane('XY').box(50, 30, 10)"

    await add_message(
        session,
        "assistant",
        "[tool_call: propose_plan]",
        plan=plan,
    )

    await add_message(
        session,
        "assistant",
        "[tool_call: propose_cadquery_code]",
        code=code,
    )

    messages = await to_openai_messages(session)

    assert messages == [
        {
            "role": "assistant",
            "content": (
                "[tool_call: propose_plan]\n\n"
                f"Proposed plan:\n{plan}"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "[tool_call: propose_cadquery_code]\n\n"
                f"Proposed CadQuery code:\n{code}"
            ),
        },
    ]


@pytest.mark.asyncio
async def test_run_agent_turn_code_proposal(db):
    session = await create_session()

    code = "result = cq.Workplane('XY').box(10, 10, 10)"
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_cadquery_code"
    mock_tool_call.function.arguments = json.dumps({
        "code": code,
        "description": "Creates a simple cube.",
    })

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Make me a cube")

    assert result == {
        "type": "code_proposal",
        "code": code,
        "description": "Creates a simple cube.",
    }

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "awaiting_code_approval"
    assert refreshed.pending_code == code


@pytest.mark.asyncio
async def test_run_agent_turn_self_correction(db):
    session = await create_session()

    corrected_code = "result = cq.Workplane('XY').box(20, 10, 5)"
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "self_correct"
    mock_tool_call.function.arguments = json.dumps({
        "error_analysis": "The original code did not assign result.",
        "corrected_code": corrected_code,
    })

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Execution failed")

    assert result == {
        "type": "self_correction",
        "error_analysis": "The original code did not assign result.",
        "code": corrected_code,
    }

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "awaiting_code_approval"
    assert refreshed.pending_code == corrected_code


@pytest.mark.asyncio
async def test_run_agent_turn_handles_unknown_tool_name(db):
    session = await create_session()

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "unknown_tool"
    mock_tool_call.function.arguments = json.dumps({"value": True})

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Make me a cube")

    assert result == {
        "type": "error",
        "content": "Unknown tool requested by model: unknown_tool",
    }

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "idle"


@pytest.mark.asyncio
async def test_run_agent_turn_disables_parallel_tool_calls(db):
    session = await create_session()

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_plan"
    mock_tool_call.function.arguments = json.dumps({
        "plan": "Create a simple cube.",
        "assumptions": [],
    })

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_create:
        await run_agent_turn(session, "Make me a cube")

    await_args = mock_create.await_args
    assert await_args is not None
    assert await_args.kwargs["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_execute_approved_code_respects_max_iterations(db):
    session = await create_session()

    session.failed_iterations = MAX_ITERATIONS
    session.pending_code = "result = cq.Workplane('XY').box(10, 10, 10)"
    await session.save()

    with patch("app.services.agent.execute_cadquery") as mock_executor:
        result = await execute_approved_code(session)
        mock_executor.assert_not_called()

    assert result["type"] == "error"
    assert str(MAX_ITERATIONS) in result["content"]

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "error"


@pytest.mark.asyncio
async def test_run_agent_turn_internal_nudge_is_not_persisted(db):
    session = await create_session()

    text_choice = MagicMock()
    text_choice.message.tool_calls = None
    text_choice.message.content = "I can do that."

    text_response = MagicMock()
    text_response.choices = [text_choice]

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_cadquery_code"
    mock_tool_call.function.arguments = json.dumps({
        "code": "result = cq.Workplane('XY').box(10, 10, 10)",
        "description": "Creates a simple cube.",
    })

    tool_choice = MagicMock()
    tool_choice.message.tool_calls = [mock_tool_call]
    tool_choice.message.content = None

    tool_response = MagicMock()
    tool_response.choices = [tool_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        side_effect=[text_response, tool_response],
    ):
        result = await run_agent_turn(session, "Make me a cube")

    assert result["type"] == "code_proposal"

    messages = await get_messages(session)
    persisted_user_messages = [
        message.content
        for message in messages
        if message.role == "user"
    ]
    assert persisted_user_messages == ["Make me a cube"]


@pytest.mark.asyncio
async def test_run_agent_turn_handles_malformed_tool_arguments(db):
    session = await create_session()

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_plan"
    mock_tool_call.function.arguments = "{not json"

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Make me a bracket")

    assert result == {
        "type": "error",
        "content": "Invalid arguments for tool propose_plan",
    }

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "idle"


@pytest.mark.asyncio
async def test_run_agent_turn_handles_tool_argument_mismatch(db):
    session = await create_session()

    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "propose_plan"
    mock_tool_call.function.arguments = json.dumps({
        "plan": "Make a simple cube.",
        "assumptions": [],
        "unexpected": True,
    })

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch(
        "app.services.agent.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await run_agent_turn(session, "Make me a cube")

    assert result == {
        "type": "error",
        "content": "Invalid arguments for tool propose_plan",
    }

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "idle"
