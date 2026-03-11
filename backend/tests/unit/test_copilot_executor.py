import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_execute_tool_unknown_returns_error():
    from app.services.copilot.executor import execute_tool
    db = AsyncMock()
    result = await execute_tool(db, uuid.uuid4(), "nonexistent_tool", {})
    assert "error" in str(result).lower() or "unknown" in str(result).lower()


@pytest.mark.asyncio
async def test_execute_fetch_chatbots_returns_list():
    from app.services.copilot.executor import execute_tool
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    workspace_id = uuid.uuid4()
    result = await execute_tool(db, workspace_id, "fetch_chatbots", {})
    assert isinstance(result, list)
