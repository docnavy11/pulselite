"""
Tenant Isolation Suite — Phase 3.

Two attack vectors:
1. WORKSPACE SUBSTITUTION (→ 403): Agent A uses their JWT but workspace B's ID in the URL.
2. IDOR (→ 404): Agent A uses workspace A's ID but workspace B's resource IDs.
"""
from tests.factories import (
    make_chatbot,
    make_knowledge_base,
    make_conversation,
    make_message,
)


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR 1: Workspace ID substitution → 403
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkspaceSubstitution:
    """Agent A substitutes workspace B's ID into the URL. Must get 403."""

    async def test_cannot_list_chatbots_in_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/chatbots")
        assert r.status_code == 403

    async def test_cannot_list_conversations_in_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/conversations")
        assert r.status_code == 403

    async def test_cannot_list_knowledge_bases_in_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/knowledge-bases")
        assert r.status_code == 403

    async def test_cannot_view_credits_balance_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/credits/balance")
        assert r.status_code == 403

    async def test_cannot_view_dashboard_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/dashboard")
        assert r.status_code == 403

    async def test_cannot_view_integrations_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/integrations")
        assert r.status_code == 403

    async def test_cannot_view_data_retention_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/data-retention")
        assert r.status_code == 403


class TestWorkspaceSubstitutionWrites:
    """Agent A cannot create/modify resources in workspace B."""

    async def test_cannot_create_chatbot_in_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/chatbots",
            json={"name": "Injected Bot", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
        )
        assert r.status_code == 403

    async def test_cannot_create_knowledge_base_in_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/knowledge-bases",
            json={"name": "Stolen KB", "chatbot_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert r.status_code == 403

    async def test_cannot_update_data_retention_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.put(
            f"/api/v1/workspaces/{second_workspace.id}/data-retention",
            json={"data_retention_days": 1},
        )
        assert r.status_code == 403

    async def test_cannot_update_integration_of_other_workspace(self, auth_client, second_workspace):
        r = await auth_client.put(
            f"/api/v1/workspaces/{second_workspace.id}/integrations/hubspot",
            json={"config": {}, "is_active": True},
        )
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR 2: IDOR — correct workspace_id, wrong resource ID → 404
# ══════════════════════════════════════════════════════════════════════════════

class TestIDOR:
    """Agent A uses their OWN workspace_id but workspace B's resource IDs."""

    async def test_cannot_read_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}")
        assert r.status_code == 404

    async def test_cannot_update_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        r = await auth_client.put(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}",
            json={"name": "Hacked"},
        )
        assert r.status_code == 404

    async def test_cannot_delete_other_workspaces_chatbot_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace, name="Bot B")
        r = await auth_client.delete(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot_b.id}")
        assert r.status_code == 404

    async def test_cannot_read_other_workspaces_knowledge_base_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        kb_b = await make_knowledge_base(db, second_workspace, bot_b, name="KB B")
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{kb_b.id}")
        assert r.status_code == 404

    async def test_cannot_read_other_workspaces_conversation_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        conv_b = await make_conversation(db, second_workspace, bot_b)
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations/{conv_b.id}")
        assert r.status_code == 404

    async def test_cannot_read_messages_of_other_workspaces_conversation_via_idor(
        self, db, auth_client, workspace, second_workspace
    ):
        bot_b = await make_chatbot(db, second_workspace)
        conv_b = await make_conversation(db, second_workspace, bot_b)
        await make_message(db, conv_b, second_workspace, content="Secret message")
        r = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/conversations/{conv_b.id}/messages"
        )
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POSITIVE CONTROLS: Agent A can access their OWN resources
# ══════════════════════════════════════════════════════════════════════════════

class TestPositiveControls:
    """Sanity checks: auth_client CAN access workspace A's resources."""

    async def test_can_list_own_chatbots(self, auth_client, workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
        assert r.status_code == 200

    async def test_can_list_own_conversations(self, auth_client, workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
        assert r.status_code == 200

    async def test_can_read_own_chatbot(self, db, auth_client, workspace):
        bot = await make_chatbot(db, workspace, name="Own Bot")
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Own Bot"

    async def test_can_read_own_credits_balance(self, auth_client, workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
        assert r.status_code == 200

    async def test_can_list_own_knowledge_bases(self, auth_client, workspace):
        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/knowledge-bases")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# NO AUTH: requests without a token → 401 or 403
# ══════════════════════════════════════════════════════════════════════════════

class TestNoAuthentication:
    """Requests with no Authorization header must be rejected."""

    async def test_unauthenticated_cannot_list_chatbots(self, client, workspace):
        r = await client.get(f"/api/v1/workspaces/{workspace.id}/chatbots")
        assert r.status_code in (401, 403)

    async def test_unauthenticated_cannot_list_conversations(self, client, workspace):
        r = await client.get(f"/api/v1/workspaces/{workspace.id}/conversations")
        assert r.status_code in (401, 403)

    async def test_unauthenticated_cannot_view_credits(self, client, workspace):
        r = await client.get(f"/api/v1/workspaces/{workspace.id}/credits/balance")
        assert r.status_code in (401, 403)

    async def test_unknown_agent_token_rejected(self, client, workspace):
        """A JWT signed with the right key but unknown agent ID must be rejected."""
        from app.utils.security import create_access_token
        import uuid
        token = create_access_token({"sub": str(uuid.uuid4()), "type": "access"})
        r = await client.get(
            f"/api/v1/workspaces/{workspace.id}/chatbots",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code in (401, 403)
