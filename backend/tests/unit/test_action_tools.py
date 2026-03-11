import uuid

from app.services.action_tools import build_tool_definitions, action_id_for_tool_name
from app.models.actions import ChatbotAction


def _make_action(action_type: str, name: str, trigger: str, parameters: list[dict]) -> ChatbotAction:
    a = ChatbotAction()
    a.id = uuid.uuid4()
    a.chatbot_id = uuid.uuid4()
    a.workspace_id = uuid.uuid4()
    a.action_type = action_type
    a.name = name
    a.trigger_description = trigger
    a.config = {}
    a.is_enabled = True
    a.parameters = parameters
    return a


def test_build_tool_definitions_basic():
    action = _make_action(
        "webhook", "Notify CRM",
        "When user wants to be contacted",
        [{"name": "email", "type": "string", "required": True, "description": "User email"}],
    )
    tools = build_tool_definitions([action])
    assert len(tools) == 1
    t = tools[0]
    assert t["type"] == "function"
    assert "email" in t["function"]["parameters"]["properties"]
    assert "email" in t["function"]["parameters"]["required"]


def test_build_tool_definitions_no_parameters():
    """Actions without parameters still produce a tool definition with no required params."""
    action = _make_action("custom_button", "Book demo", "When user wants a demo", [])
    tools = build_tool_definitions([action])
    assert len(tools) == 1
    assert tools[0]["function"]["parameters"]["required"] == []


def test_tool_name_is_stable_and_unique():
    action = _make_action("webhook", "My Webhook", "trigger", [])
    name = build_tool_definitions([action])[0]["function"]["name"]
    # Name is derived from action id — stable across calls
    assert action_id_for_tool_name(name) == str(action.id)


def test_action_id_for_tool_name_invalid():
    assert action_id_for_tool_name("not_a_tool") is None
    assert action_id_for_tool_name("pulse_short") is None
