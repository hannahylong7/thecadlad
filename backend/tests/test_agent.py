import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tortoise import Tortoise

from app.services.agent import _extract_code_block, run_agent_turn, execute_approved_code
from app.models.session import create_session, MAX_ITERATIONS
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


# Test 1: _extract_code_block

def test_extract_code_block_finds_cadquery_code():
    text = """
    Here is the corrected code:
 
    ```python
    result = cq.Workplane("XY").box(50, 30, 10)
    ```
 
    Please execute this.
    """
    extracted = _extract_code_block(text)
    assert extracted == 'result = cq.Workplane("XY").box(50, 30, 10)'
 
 
def test_extract_code_block_returns_none_when_no_code():
    text = "What dimensions would you like for the bracket?"
    assert _extract_code_block(text) is None
 
 
def test_extract_code_block_ignores_non_cadquery_code():
    text = """
    ```python
    print("hello world")
    ```
    """
    assert _extract_code_block(text) is None


# Test 2: run_agent_turn state transition

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


# Test 3: MAX_ITERATIONS enforcement

@pytest.mark.asyncio
async def test_execute_approved_code_respects_max_iterations(db):
    session = await create_session()

    session.iteration = MAX_ITERATIONS
    session.pending_code = "result = cq.Workplane('XY').box(10, 10, 10)"
    await session.save()

    with patch("app.services.agent.execute_cadquery") as mock_executor:
        result = await execute_approved_code(session)
        mock_executor.assert_not_called()

    assert result["type"] == "error"
    assert str(MAX_ITERATIONS) in result["content"]

    refreshed = await Session.get(id=session.id)
    assert refreshed.status == "error"