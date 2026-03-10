"""Integration tests for credits balance and history endpoints."""


async def test_get_credits_balance_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data
    assert isinstance(data["balance"], int)


async def test_credits_balance_has_used_this_month(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    data = r.json()
    assert "used_this_month" in data


async def test_credits_balance_is_non_negative(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
    assert r.json()["balance"] >= 0


async def test_get_credits_history_returns_200(auth_client, workspace):
    r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/history")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))
