"""Tests for action execution — webhook, slack, stripe, salesforce, client-side, LLM trigger, and run_actions."""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.action_executor import (
    _execute_slack,
    _execute_stripe_lookup,
    _execute_salesforce_ticket,
    _execute_webhook,
    _ask_llm_trigger,
    build_client_payload,
    compute_signature,
    execute_action,
    run_actions,
    CLIENT_SIDE_TYPES,
    SERVER_SIDE_TYPES,
)


def _make_action(**overrides):
    """Create a mock ChatbotAction."""
    action = MagicMock()
    action.id = overrides.get("id", uuid.uuid4())
    action.name = overrides.get("name", "Test Action")
    action.action_type = overrides.get("action_type", "webhook")
    action.trigger_description = overrides.get("trigger_description", "When user asks for help")
    action.config = overrides.get("config", {"url": "https://example.com/hook", "method": "POST"})
    action.is_enabled = overrides.get("is_enabled", True)
    action.parameters = overrides.get("parameters", [])
    action.chatbot_id = overrides.get("chatbot_id", uuid.uuid4())
    action.workspace_id = overrides.get("workspace_id", uuid.uuid4())
    return action


def _mock_httpx(response_code=200, side_effect=None):
    """Helper to mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    if side_effect:
        mock_client.post.side_effect = side_effect
        mock_client.get.side_effect = side_effect
    else:
        mock_client.post.return_value = httpx.Response(response_code)
        mock_client.get.return_value = httpx.Response(response_code)

    patcher = patch("app.services.action_executor.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher, mock_client


# ─── Webhook ───────────────────────────────────────────────────

class TestWebhookExecution:

    async def test_post_sends_correct_payload(self):
        action = _make_action(name="My Hook", config={"url": "https://example.com/hook", "method": "POST"})
        context = {"conversation_id": "conv-123", "message": "Help me", "response": "Sure!"}
        patcher, mock = _mock_httpx(200)
        try:
            status = await _execute_webhook(action, context)
            assert status == "ok"
            payload = mock.post.call_args.kwargs["json"]
            assert payload["action"] == "My Hook"
            assert payload["conversation_id"] == "conv-123"
            assert payload["message"] == "Help me"
            assert payload["response"] == "Sure!"
            assert payload["action_id"] == str(action.id)
        finally:
            patcher.stop()

    async def test_rejects_http_urls(self):
        action = _make_action(config={"url": "http://example.com/hook"})
        assert await _execute_webhook(action, {}) == "error:url_must_be_https"

    async def test_rejects_empty_url(self):
        action = _make_action(config={"url": ""})
        assert await _execute_webhook(action, {}) == "error:no_url"

    async def test_rejects_missing_url(self):
        action = _make_action(config={})
        assert await _execute_webhook(action, {}) == "error:no_url"

    async def test_handles_server_error(self):
        action = _make_action(config={"url": "https://example.com/hook", "method": "POST"})
        patcher, _ = _mock_httpx(500)
        try:
            assert await _execute_webhook(action, {}) == "error:500"
        finally:
            patcher.stop()

    async def test_handles_network_failure(self):
        action = _make_action(config={"url": "https://example.com/hook", "method": "POST"})
        patcher, _ = _mock_httpx(side_effect=httpx.ConnectError("refused"))
        try:
            assert await _execute_webhook(action, {}) == "error:request_failed"
        finally:
            patcher.stop()

    async def test_handles_timeout(self):
        action = _make_action(config={"url": "https://example.com/hook", "method": "POST"})
        patcher, _ = _mock_httpx(side_effect=httpx.ReadTimeout("timeout"))
        try:
            assert await _execute_webhook(action, {}) == "error:request_failed"
        finally:
            patcher.stop()

    async def test_get_method(self):
        action = _make_action(config={"url": "https://example.com/hook", "method": "GET"})
        patcher, mock = _mock_httpx(200)
        try:
            assert await _execute_webhook(action, {"message": "test"}) == "ok"
            mock.get.assert_called_once()
            mock.post.assert_not_called()
        finally:
            patcher.stop()

    async def test_hmac_signature_sent(self):
        secret = "webhook-secret-123"
        action = _make_action(config={"url": "https://example.com/hook", "method": "POST", "secret": secret})
        patcher, mock = _mock_httpx(200)
        try:
            await _execute_webhook(action, {"message": "test"})
            headers = mock.post.call_args.kwargs["headers"]
            assert "X-PulseLite-Signature" in headers
            sig = headers["X-PulseLite-Signature"]
            assert sig.startswith("sha256=")
            # Verify it matches
            payload = mock.post.call_args.kwargs["json"]
            assert sig == f"sha256={compute_signature(secret, payload)}"
        finally:
            patcher.stop()

    async def test_no_signature_without_secret(self):
        action = _make_action(config={"url": "https://example.com/hook", "method": "POST"})
        patcher, mock = _mock_httpx(200)
        try:
            await _execute_webhook(action, {})
            headers = mock.post.call_args.kwargs["headers"]
            assert "X-PulseLite-Signature" not in headers
        finally:
            patcher.stop()


# ─── Slack ─────────────────────────────────────────────────────

class TestSlackExecution:

    async def test_sends_to_inline_webhook(self):
        action = _make_action(
            action_type="slack_message",
            config={"webhook_url": "https://hooks.slack.com/inline", "message_template": "Alert: {action}"},
        )
        patcher, mock = _mock_httpx(200)
        try:
            status = await _execute_slack(action, {"message": "hi"}, workspace_slack_webhook=None)
            assert status == "ok"
            payload = mock.post.call_args.kwargs["json"]
            assert "Alert: Test Action" in payload["text"]
        finally:
            patcher.stop()

    async def test_falls_back_to_workspace_webhook(self):
        action = _make_action(action_type="slack_message", config={"message_template": "{action} fired"})
        patcher, mock = _mock_httpx(200)
        try:
            status = await _execute_slack(action, {}, workspace_slack_webhook="https://hooks.slack.com/ws")
            assert status == "ok"
            call_url = mock.post.call_args[0][0]
            assert call_url == "https://hooks.slack.com/ws"
        finally:
            patcher.stop()

    async def test_error_no_webhook(self):
        action = _make_action(action_type="slack_message", config={})
        status = await _execute_slack(action, {}, workspace_slack_webhook=None)
        assert status == "error:no_webhook_url"

    async def test_template_with_context(self):
        action = _make_action(
            action_type="slack_message",
            name="Escalation",
            config={"webhook_url": "https://hooks.slack.com/t", "message_template": "User said: {message}"},
        )
        patcher, mock = _mock_httpx(200)
        try:
            await _execute_slack(action, {"message": "I need a human"}, None)
            text = mock.post.call_args.kwargs["json"]["text"]
            assert text == "User said: I need a human"
        finally:
            patcher.stop()

    async def test_template_missing_key_falls_back(self):
        action = _make_action(
            action_type="slack_message",
            name="Fallback",
            config={"webhook_url": "https://hooks.slack.com/t", "message_template": "Got: {nonexistent_key}"},
        )
        patcher, mock = _mock_httpx(200)
        try:
            await _execute_slack(action, {}, None)
            text = mock.post.call_args.kwargs["json"]["text"]
            assert "Fallback" in text  # falls back to action name
        finally:
            patcher.stop()

    async def test_handles_slack_api_error(self):
        action = _make_action(
            action_type="slack_message",
            config={"webhook_url": "https://hooks.slack.com/t"},
        )
        patcher, _ = _mock_httpx(403)
        try:
            assert await _execute_slack(action, {}, None) == "error:403"
        finally:
            patcher.stop()

    async def test_handles_network_failure(self):
        action = _make_action(
            action_type="slack_message",
            config={"webhook_url": "https://hooks.slack.com/t"},
        )
        patcher, _ = _mock_httpx(side_effect=httpx.ConnectError("refused"))
        try:
            assert await _execute_slack(action, {}, None) == "error:request_failed"
        finally:
            patcher.stop()


# ─── Stripe Lookup ─────────────────────────────────────────────

class TestStripeLookup:

    async def test_no_db_session(self):
        action = _make_action(action_type="stripe_lookup")
        status = await _execute_stripe_lookup(action, {"email": "a@b.com"}, db_session=None)
        assert status == "error:no_db_session"

    async def test_stripe_not_configured(self):
        action = _make_action(action_type="stripe_lookup")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock
        status = await _execute_stripe_lookup(action, {"email": "a@b.com"}, db_session=db)
        assert status == "error:stripe_not_configured"

    async def test_no_email(self):
        action = _make_action(action_type="stripe_lookup")
        db = AsyncMock()
        integration = MagicMock()
        integration.config = {"api_key": "encrypted_key"}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = integration
        db.execute.return_value = result_mock
        status = await _execute_stripe_lookup(action, {}, db_session=db)
        assert status == "error:no_email"

    async def test_successful_lookup(self):
        action = _make_action(action_type="stripe_lookup")
        db = AsyncMock()
        integration = MagicMock()
        integration.config = {"api_key": "encrypted_key"}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = integration
        db.execute.return_value = result_mock

        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        mock_price = MagicMock()
        mock_price.nickname = "Pro"
        mock_item = MagicMock()
        mock_item.price = mock_price
        mock_sub = MagicMock()
        mock_sub.items.data = [mock_item]

        with patch("app.services.action_executor.decrypt_api_key", return_value="sk_test_xxx"):
            with patch("app.services.action_executor._execute_stripe_lookup.__module__", create=True):
                import importlib
                # Mock stripe module
                mock_stripe = MagicMock()
                mock_stripe.Customer.list.return_value = MagicMock(data=[mock_customer])
                mock_stripe.Subscription.list.return_value = MagicMock(data=[mock_sub])
                with patch.dict("sys.modules", {"stripe": mock_stripe}):
                    status = await _execute_stripe_lookup(action, {"email": "user@test.com"}, db_session=db)
                    assert status == "ok:plan=Pro"


# ─── Salesforce Ticket ─────────────────────────────────────────

class TestSalesforceTicket:

    async def test_no_db_session(self):
        action = _make_action(action_type="salesforce_ticket")
        status = await _execute_salesforce_ticket(action, {}, db_session=None)
        assert status == "error:no_db_session"

    async def test_salesforce_not_configured(self):
        action = _make_action(action_type="salesforce_ticket")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock
        status = await _execute_salesforce_ticket(action, {}, db_session=db)
        assert status == "error:salesforce_not_configured"

    async def test_successful_ticket_creation(self):
        action = _make_action(action_type="salesforce_ticket")
        db = AsyncMock()
        integration = MagicMock()
        integration.config = {
            "username": "enc_user",
            "password": "enc_pass",
            "security_token": "enc_token",
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = integration
        db.execute.return_value = result_mock

        mock_sf = MagicMock()
        mock_sf_cls = MagicMock(return_value=mock_sf)

        with patch("app.services.action_executor.decrypt_api_key", side_effect=lambda x: f"dec_{x}"):
            with patch.dict("sys.modules", {"simple_salesforce": MagicMock(Salesforce=mock_sf_cls)}):
                status = await _execute_salesforce_ticket(
                    action, {"message": "I need help", "email": "user@test.com"}, db_session=db
                )
                assert status == "ok"
                mock_sf.Case.create.assert_called_once()
                case_data = mock_sf.Case.create.call_args[0][0]
                assert "Chat inquiry:" in case_data["Subject"]
                assert case_data["SuppliedEmail"] == "user@test.com"
                assert case_data["Origin"] == "Web"

    async def test_salesforce_api_failure(self):
        action = _make_action(action_type="salesforce_ticket")
        db = AsyncMock()
        integration = MagicMock()
        integration.config = {"username": "u", "password": "p", "security_token": "t"}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = integration
        db.execute.return_value = result_mock

        mock_sf_cls = MagicMock(side_effect=Exception("auth failed"))
        with patch("app.services.action_executor.decrypt_api_key", return_value="x"):
            with patch.dict("sys.modules", {"simple_salesforce": MagicMock(Salesforce=mock_sf_cls)}):
                status = await _execute_salesforce_ticket(action, {"message": "help"}, db_session=db)
                assert status == "error:salesforce_api_failed"


# ─── Client-Side Actions ──────────────────────────────────────

class TestClientSideActions:

    async def test_all_client_types_return_client_status(self):
        for action_type in CLIENT_SIDE_TYPES:
            action = _make_action(action_type=action_type, config={"key": "val"})
            status, payload = await execute_action(action, {})
            assert status == "client", f"{action_type} should return 'client' status"
            assert payload is not None, f"{action_type} should return payload"
            assert payload["type"] == action_type

    async def test_build_client_payload_structure(self):
        aid = uuid.uuid4()
        action = _make_action(
            id=aid,
            name="Book Meeting",
            action_type="calendly",
            config={"url": "https://calendly.com/test", "button_text": "Schedule"},
        )
        payload = build_client_payload(action)
        assert payload["action_id"] == str(aid)
        assert payload["type"] == "calendly"
        assert payload["name"] == "Book Meeting"
        assert payload["config"]["url"] == "https://calendly.com/test"

    async def test_custom_button_payload(self):
        action = _make_action(
            action_type="custom_button",
            config={"label": "Click me", "url": "https://example.com"},
        )
        status, payload = await execute_action(action, {})
        assert status == "client"
        assert payload["config"]["label"] == "Click me"

    async def test_custom_tool_payload(self):
        action = _make_action(action_type="custom_tool", config={"tool_id": "abc"})
        status, payload = await execute_action(action, {})
        assert status == "client"
        assert payload["type"] == "custom_tool"

    async def test_calcom_payload(self):
        action = _make_action(action_type="calcom", config={"link": "https://cal.com/user"})
        status, payload = await execute_action(action, {})
        assert status == "client"
        assert payload["type"] == "calcom"


# ─── Execute Action Dispatcher ─────────────────────────────────

class TestExecuteActionDispatcher:

    async def test_dispatches_webhook(self):
        action = _make_action(action_type="webhook")
        with patch("app.services.action_executor._execute_webhook", new_callable=AsyncMock, return_value="ok"):
            status, payload = await execute_action(action, {"msg": "hi"})
            assert status == "ok"
            assert payload is None

    async def test_dispatches_slack(self):
        action = _make_action(action_type="slack_message")
        with patch("app.services.action_executor._execute_slack", new_callable=AsyncMock, return_value="ok"):
            status, _ = await execute_action(action, {}, workspace_slack_webhook="https://hooks.slack.com/x")
            assert status == "ok"

    async def test_dispatches_stripe(self):
        action = _make_action(action_type="stripe_lookup")
        with patch("app.services.action_executor._execute_stripe_lookup", new_callable=AsyncMock, return_value="ok:plan=Pro"):
            status, _ = await execute_action(action, {}, db_session=AsyncMock())
            assert status == "ok:plan=Pro"

    async def test_dispatches_salesforce(self):
        action = _make_action(action_type="salesforce_ticket")
        with patch("app.services.action_executor._execute_salesforce_ticket", new_callable=AsyncMock, return_value="ok"):
            status, _ = await execute_action(action, {}, db_session=AsyncMock())
            assert status == "ok"

    async def test_unknown_type_returns_error(self):
        action = _make_action(action_type="nonexistent")
        status, payload = await execute_action(action, {})
        assert status == "error:unknown_type"
        assert payload is None


# ─── LLM Trigger ──────────────────────────────────────────────

class TestLLMTrigger:

    async def test_returns_true_on_yes(self):
        with patch("app.services.action_executor.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.generate.return_value = "yes"
            mock_get.return_value = mock_client
            result = await _ask_llm_trigger("User: help\nBot: sure", "When user needs help", "model-x")
            assert result is True

    async def test_returns_false_on_no(self):
        with patch("app.services.action_executor.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.generate.return_value = "no"
            mock_get.return_value = mock_client
            result = await _ask_llm_trigger("User: hi\nBot: hello", "When user is angry", "model-x")
            assert result is False

    async def test_returns_false_on_llm_error(self):
        with patch("app.services.action_executor.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = Exception("API down")
            mock_get.return_value = mock_client
            result = await _ask_llm_trigger("conv", "trigger", "model-x")
            assert result is False

    async def test_case_insensitive_yes(self):
        with patch("app.services.action_executor.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.generate.return_value = "Yes."
            mock_get.return_value = mock_client
            assert await _ask_llm_trigger("conv", "trigger", "m") is True

    async def test_yes_with_whitespace(self):
        with patch("app.services.action_executor.get_llm_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.generate.return_value = "  YES  "
            mock_get.return_value = mock_client
            assert await _ask_llm_trigger("conv", "trigger", "m") is True


# ─── run_actions (full pipeline) ───────────────────────────────

class TestRunActions:

    async def test_no_actions_returns_empty(self):
        db = AsyncMock()
        with patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[]):
            result = await run_actions(
                db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "hello", "hi there"
            )
            assert result == []

    async def test_triggered_webhook_fires_and_logs_event(self):
        wid = uuid.uuid4()
        cid = uuid.uuid4()
        bid = uuid.uuid4()
        conv_id = uuid.uuid4()
        action = _make_action(id=uuid.uuid4(), workspace_id=wid, chatbot_id=bid, action_type="webhook")

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[action]):
            with patch("app.services.action_executor._get_workspace_slack_webhook", new_callable=AsyncMock, return_value=None):
                with patch("app.services.action_executor.get_internal_model", new_callable=AsyncMock, return_value="fast-model"):
                    with patch("app.services.action_executor._ask_llm_trigger", new_callable=AsyncMock, return_value=True):
                        with patch("app.services.action_executor._execute_webhook", new_callable=AsyncMock, return_value="ok"):
                            result = await run_actions(db, wid, bid, conv_id, "help me", "sure thing")

                            # No client payloads for webhook
                            assert result == []
                            # ActionEvent was logged
                            db.add.assert_called_once()
                            event = db.add.call_args[0][0]
                            assert event.action_type == "webhook"
                            assert event.status == "ok"
                            assert event.conversation_id == conv_id
                            db.flush.assert_called_once()

    async def test_not_triggered_action_doesnt_fire(self):
        action = _make_action(action_type="webhook")
        db = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[action]):
            with patch("app.services.action_executor._get_workspace_slack_webhook", new_callable=AsyncMock, return_value=None):
                with patch("app.services.action_executor.get_internal_model", new_callable=AsyncMock, return_value="m"):
                    with patch("app.services.action_executor._ask_llm_trigger", new_callable=AsyncMock, return_value=False):
                        result = await run_actions(db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "hi", "hello")
                        assert result == []
                        db.add.assert_not_called()

    async def test_client_side_action_returns_payload(self):
        action = _make_action(action_type="collect_lead", config={"fields": ["email", "name"]})
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[action]):
            with patch("app.services.action_executor._get_workspace_slack_webhook", new_callable=AsyncMock, return_value=None):
                with patch("app.services.action_executor.get_internal_model", new_callable=AsyncMock, return_value="m"):
                    with patch("app.services.action_executor._ask_llm_trigger", new_callable=AsyncMock, return_value=True):
                        result = await run_actions(db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "hi", "hello")
                        assert len(result) == 1
                        assert result[0]["type"] == "collect_lead"

    async def test_multiple_actions_mixed_types(self):
        webhook = _make_action(action_type="webhook", name="Hook")
        lead = _make_action(action_type="collect_lead", name="Lead", config={"fields": ["email"]})
        slack = _make_action(action_type="slack_message", name="Slack", config={"webhook_url": "https://hooks.slack.com/t"})

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.action_service.list_enabled_actions", new_callable=AsyncMock, return_value=[webhook, lead, slack]):
            with patch("app.services.action_executor._get_workspace_slack_webhook", new_callable=AsyncMock, return_value=None):
                with patch("app.services.action_executor.get_internal_model", new_callable=AsyncMock, return_value="m"):
                    with patch("app.services.action_executor._ask_llm_trigger", new_callable=AsyncMock, return_value=True):
                        with patch("app.services.action_executor._execute_webhook", new_callable=AsyncMock, return_value="ok"):
                            with patch("app.services.action_executor._execute_slack", new_callable=AsyncMock, return_value="ok"):
                                result = await run_actions(db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "msg", "resp")
                                # Only collect_lead returns client payload
                                assert len(result) == 1
                                assert result[0]["type"] == "collect_lead"
                                # All 3 actions logged
                                assert db.add.call_count == 3


# ─── HMAC Signature ───────────────────────────────────────────

class TestComputeSignature:

    def test_deterministic(self):
        payload = {"action": "test", "message": "hello"}
        assert compute_signature("secret", payload) == compute_signature("secret", payload)

    def test_different_secrets(self):
        payload = {"action": "test"}
        assert compute_signature("s1", payload) != compute_signature("s2", payload)

    def test_different_payloads(self):
        assert compute_signature("s", {"a": 1}) != compute_signature("s", {"a": 2})

    def test_matches_manual_hmac(self):
        payload = {"action": "test", "key": "value"}
        secret = "my-secret"
        sig = compute_signature(secret, payload)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert sig == expected

    def test_sort_keys_matters(self):
        """Signature is consistent regardless of key insertion order."""
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        assert compute_signature("s", p1) == compute_signature("s", p2)


# ─── Constants ─────────────────────────────────────────────────

class TestConstants:

    def test_server_side_types(self):
        assert "webhook" in SERVER_SIDE_TYPES
        assert "slack_message" in SERVER_SIDE_TYPES

    def test_client_side_types(self):
        assert "collect_lead" in CLIENT_SIDE_TYPES
        assert "custom_button" in CLIENT_SIDE_TYPES
        assert "calendly" in CLIENT_SIDE_TYPES
        assert "calcom" in CLIENT_SIDE_TYPES
        assert "custom_tool" in CLIENT_SIDE_TYPES

    def test_no_overlap(self):
        assert SERVER_SIDE_TYPES.isdisjoint(CLIENT_SIDE_TYPES)
