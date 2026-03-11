import json
import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent
from app.services.copilot.executor import execute_tool
from app.services.copilot.system_prompt import build_system_prompt
from app.services.copilot.tools import (
    CLIENT_SIDE_TOOLS,
    get_client_side_tool_definitions,
    get_tool_definitions,
)
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["copilot"])

COPILOT_MODEL = "openai/gpt-4o-mini"
MAX_TOOL_ROUNDS = 10  # safety cap on tool-calling loop


class CopilotRequest(BaseModel):
    messages: list[dict]
    context: dict
    workspace_id: uuid.UUID


@router.post("/copilot/chat")
async def copilot_chat(
    body: CopilotRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    system_prompt = build_system_prompt(body.context)
    messages: list[dict] = [{"role": "system", "content": system_prompt}] + body.messages
    all_tools = get_tool_definitions() + get_client_side_tool_definitions()
    llm = get_llm_client("openrouter")

    async def stream():
        rounds = 0
        while rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            try:
                result = await llm.generate_with_tools(
                    messages=messages,
                    model=COPILOT_MODEL,
                    tools=all_tools,
                    temperature=0.3,
                    max_tokens=2000,
                )
            except Exception as exc:
                logger.exception("LLM call failed in copilot stream")
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "data": "LLM call failed. Please try again."}),
                }
                return

            if result["type"] == "message":
                content = result["content"]
                # Stream word by word for better UX
                words = content.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield {"event": "token", "data": json.dumps({"type": "token", "data": chunk})}
                yield {"event": "done", "data": json.dumps({"type": "done"})}
                return

            elif result["type"] == "tool_call":
                tool_name = result["tool_name"]
                args = result["arguments"]
                tool_call_id = result["tool_call_id"]

                # Append assistant tool_call message
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(args)},
                        }
                    ],
                })

                if tool_name in CLIENT_SIDE_TOOLS:
                    # Emit action event to frontend
                    yield {
                        "event": "action",
                        "data": json.dumps({"tool": tool_name, "args": args}),
                    }
                    # Tell LLM the action was dispatched
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"ok": True}),
                    })
                else:
                    # Execute server-side and feed result back
                    tool_result = await execute_tool(db, workspace_id, tool_name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(tool_result),
                    })
                # Loop: LLM continues with tool result in context

        # Hit MAX_TOOL_ROUNDS without finishing
        yield {"event": "error", "data": json.dumps({"type": "error", "data": "Max tool rounds exceeded"})}

    return EventSourceResponse(stream())
