from app.services.copilot.system_prompt import build_system_prompt


def test_system_prompt_contains_page():
    ctx = {"page": "dashboard", "data": {"total_conversations": 10}}
    prompt = build_system_prompt(ctx)
    assert "dashboard" in prompt.lower()


def test_system_prompt_contains_tool_guidance():
    ctx = {"page": "chatbot-settings", "chatbot_id": "abc", "data": {}}
    prompt = build_system_prompt(ctx)
    assert "render_panel" in prompt or "tool" in prompt.lower()


def test_system_prompt_contains_context_data():
    ctx = {"page": "dashboard", "data": {"total_conversations": 42}}
    prompt = build_system_prompt(ctx)
    assert "42" in prompt
