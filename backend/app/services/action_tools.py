"""
Convert ChatbotAction objects into OpenAI-compatible tool definitions.

Tool names encode the action UUID so we can look up the action after the LLM
returns a tool call. Format: "pulse_<uuid_hex>" (no hyphens — OpenAI names
must match [a-zA-Z0-9_-]{1,64}).
"""

import uuid

from app.models.actions import ChatbotAction

_JSON_TYPE_MAP = {"string": "string", "number": "number", "boolean": "boolean"}


def _tool_name(action_id: uuid.UUID) -> str:
    return f"pulse_{action_id.hex}"


def action_id_for_tool_name(name: str) -> str | None:
    """Reverse: extract action UUID string from tool name, or None if not valid."""
    if name.startswith("pulse_") and len(name) == 38:  # "pulse_" + 32 hex chars
        try:
            return str(uuid.UUID(name[6:]))
        except ValueError:
            return None
    return None


def build_tool_definitions(actions: list[ChatbotAction]) -> list[dict]:
    """Return OpenAI-format tool definitions for a list of actions."""
    tools = []
    for action in actions:
        properties: dict = {}
        required: list[str] = []

        for param in action.parameters or []:
            pname = param.get("name", "")
            if not pname:
                continue
            properties[pname] = {
                "type": _JSON_TYPE_MAP.get(param.get("type", "string"), "string"),
                "description": param.get("description", ""),
            }
            if param.get("required", False):
                required.append(pname)

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": _tool_name(action.id),
                    "description": action.trigger_description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return tools
