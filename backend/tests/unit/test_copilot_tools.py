from app.services.copilot.tools import get_tool_definitions, CLIENT_SIDE_TOOLS


def test_all_server_tools_have_description():
    defs = get_tool_definitions()
    for t in defs:
        assert t["type"] == "function"
        assert t["function"]["description"]


def test_client_side_tools_not_in_server_definitions():
    defs = get_tool_definitions()
    names = {t["function"]["name"] for t in defs}
    for cs in CLIENT_SIDE_TOOLS:
        assert cs not in names


def test_fetch_conversations_has_filters_param():
    defs = get_tool_definitions()
    by_name = {t["function"]["name"]: t for t in defs}
    assert "fetch_conversations" in by_name
    params = by_name["fetch_conversations"]["function"]["parameters"]["properties"]
    assert "filters" in params
