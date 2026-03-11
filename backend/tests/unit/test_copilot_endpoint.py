import pytest


def test_copilot_request_schema():
    from app.api.v1.copilot import CopilotRequest
    req = CopilotRequest(
        messages=[{"role": "user", "content": "hello"}],
        context={"page": "dashboard", "data": {}},
        workspace_id="350863e7-3dc8-430e-bc23-fd41d4499d7b",
    )
    assert req.messages[0]["role"] == "user"
    assert req.context["page"] == "dashboard"
