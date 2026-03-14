# backend/tests/unit/test_intelligence_config.py
import pytest


@pytest.mark.asyncio
async def test_update_report_config(auth_client, workspace):
    """Report config fields are saved and returned."""
    response = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/intelligence/config",
        json={
            "report_frequency": "weekly",
            "report_recipients": ["admin@example.com", "team@example.com"],
            "report_sections": {
                "conversations": True,
                "confidence": True,
                "sentiment": False,
                "gaps": True,
                "top_topics": False,
                "qa_performance": True,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["report_frequency"] == "weekly"
    assert data["report_recipients"] == ["admin@example.com", "team@example.com"]
    assert data["report_sections"]["sentiment"] is False
    assert data["report_sections"]["conversations"] is True


@pytest.mark.asyncio
async def test_get_report_config_defaults(auth_client, workspace):
    """Report config returns defaults when not configured."""
    response = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/intelligence/config"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["report_frequency"] == "off"
    assert data["report_recipients"] == []
    assert data["report_sections"]["conversations"] is True


@pytest.mark.asyncio
async def test_invalid_report_frequency(auth_client, workspace):
    """Invalid frequency is rejected."""
    response = await auth_client.put(
        f"/api/v1/workspaces/{workspace.id}/intelligence/config",
        json={"report_frequency": "biweekly"},
    )
    assert response.status_code == 422
