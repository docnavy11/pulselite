"""
Execute chatbot actions post-response.

Server-side types  (webhook, slack_message): make outbound HTTP calls.
Client-side types  (collect_lead, custom_button, calendly, calcom, custom_tool): return
  payload dicts that will be sent as SSE "action" events to the widget.
"""

import hashlib
import hmac as hmac_lib
import json
import logging
import uuid
from typing import Any

import httpx

from app.models.actions import ActionEvent, ChatbotAction
from app.services.encryption import decrypt_api_key
from app.services.llm import get_internal_client, get_internal_model

logger = logging.getLogger(__name__)

SERVER_SIDE_TYPES = {"webhook", "slack_message"}
CLIENT_SIDE_TYPES = {"collect_lead", "custom_button", "calendly", "calcom", "custom_tool"}


def compute_signature(secret: str, payload: dict) -> str:
    """Return hex SHA-256 HMAC of JSON-serialised payload."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac_lib.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def build_client_payload(action: ChatbotAction) -> dict[str, Any]:
    """Build the SSE payload for a client-side action."""
    return {
        "action_id": str(action.id),
        "type": action.action_type,
        "name": action.name,
        "config": action.config,
    }


async def _ask_llm_trigger(conversation_text: str, trigger_description: str, model: str) -> bool:
    """Ask a fast LLM whether the action should fire. Returns True/False."""
    client = get_internal_client()
    prompt = (
        f"Conversation:\n{conversation_text}\n\n"
        f'Action trigger: "{trigger_description}"\n\n'
        "Should this action trigger based on the conversation above? "
        "Reply with exactly one word: yes or no."
    )
    try:
        answer = await client.generate(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            max_tokens=5,
        )
        return answer.strip().lower().startswith("yes")
    except Exception:
        logger.exception("LLM trigger check failed")
        return False


async def _execute_webhook(action: ChatbotAction, context: dict[str, Any]) -> str:
    url = action.config.get("url", "").strip()
    if not url:
        return "error:no_url"
    if not url.startswith("https://"):
        return "error:url_must_be_https"
    method = action.config.get("method", "POST").upper()
    payload = {"action": action.name, "action_id": str(action.id), **context}

    headers: dict[str, str] = {"Content-Type": "application/json"}
    secret = action.config.get("secret", "").strip()
    if secret:
        headers["X-PulseLite-Signature"] = f"sha256={compute_signature(secret, payload)}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                r = await client.post(url, json=payload, headers=headers)
            else:
                r = await client.get(url, params={k: str(v) for k, v in payload.items()})
        return "ok" if r.is_success else f"error:{r.status_code}"
    except Exception:
        logger.warning("Webhook action %s failed", action.id, exc_info=True)
        return "error:request_failed"


async def _execute_slack(
    action: ChatbotAction,
    context: dict[str, Any],
    workspace_slack_webhook: str | None,
) -> str:
    # Prefer inline webhook_url; fall back to workspace integration
    webhook_url = action.config.get("webhook_url", "").strip() or workspace_slack_webhook
    if not webhook_url:
        return "error:no_webhook_url"

    template = action.config.get("message_template", "Action triggered: {action}")
    try:
        text = template.format(action=action.name, **context)
    except KeyError:
        text = f"Action triggered: {action.name}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json={"text": text})
        return "ok" if r.is_success else f"error:{r.status_code}"
    except Exception:
        logger.warning("Slack action %s failed", action.id, exc_info=True)
        return "error:request_failed"


async def _execute_stripe_lookup(action: ChatbotAction, context: dict[str, Any], db_session: Any) -> str:
    """Look up a Stripe customer by email and return subscription status."""
    from sqlalchemy import select

    from app.models.integrations import IntegrationConfig

    if db_session is None:
        return "error:no_db_session"

    result = await db_session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == action.workspace_id,
            IntegrationConfig.integration_type == "stripe",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()
    if not integration or not integration.config.get("api_key"):
        return "error:stripe_not_configured"

    email = context.get("email", "")
    if not email:
        return "error:no_email"

    try:
        import stripe  # type: ignore[import]

        stripe.api_key = decrypt_api_key(integration.config["api_key"])
        customers = stripe.Customer.list(email=email, limit=1)
        if not customers.data:
            return "ok:no_customer"
        customer = customers.data[0]
        subs = stripe.Subscription.list(customer=customer.id, status="active", limit=1)
        plan = subs.data[0].items.data[0].price.nickname if subs.data else "none"
        return f"ok:plan={plan}"
    except Exception:
        logger.warning("Stripe lookup failed", exc_info=True)
        return "error:stripe_api_failed"


async def _execute_salesforce_ticket(action: ChatbotAction, context: dict[str, Any], db_session: Any) -> str:
    """Create a Salesforce Case from the current conversation context."""
    from sqlalchemy import select

    from app.models.integrations import IntegrationConfig

    if db_session is None:
        return "error:no_db_session"

    result = await db_session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == action.workspace_id,
            IntegrationConfig.integration_type == "salesforce",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        return "error:salesforce_not_configured"

    cfg = integration.config
    try:
        from simple_salesforce import Salesforce  # type: ignore[import]

        sf = Salesforce(
            username=decrypt_api_key(cfg["username"]) if cfg.get("username") else None,
            password=decrypt_api_key(cfg["password"]) if cfg.get("password") else None,
            security_token=decrypt_api_key(cfg["security_token"]) if cfg.get("security_token") else None,
        )
        sf.Case.create(
            {
                "Subject": f"Chat inquiry: {context.get('message', '')[:80]}",
                "Description": context.get("message", ""),
                "Origin": "Web",
                "SuppliedEmail": context.get("email", ""),
            }
        )
        return "ok"
    except Exception:
        logger.warning("Salesforce ticket creation failed", exc_info=True)
        return "error:salesforce_api_failed"


async def execute_action(
    action: ChatbotAction,
    context: dict[str, Any],
    workspace_slack_webhook: str | None = None,
    db_session: Any = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    Execute a single action.

    Returns (status, client_payload).
    - status: "ok" | "error:..." | "client"
    - client_payload: set for client-side types, None for server-side
    """
    if action.action_type == "webhook":
        status = await _execute_webhook(action, context)
        return status, None

    if action.action_type == "slack_message":
        status = await _execute_slack(action, context, workspace_slack_webhook)
        return status, None

    if action.action_type == "stripe_lookup":
        status = await _execute_stripe_lookup(action, context, db_session)
        return status, None

    if action.action_type == "salesforce_ticket":
        status = await _execute_salesforce_ticket(action, context, db_session)
        return status, None

    if action.action_type in CLIENT_SIDE_TYPES:
        return "client", build_client_payload(action)

    return "error:unknown_type", None


async def _get_workspace_slack_webhook(db_session, workspace_id: uuid.UUID) -> str | None:
    """Look up the workspace Slack integration webhook URL."""
    from sqlalchemy import select

    from app.models.integrations import IntegrationConfig

    result = await db_session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type.in_(["slack", "slack_bot"]),
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    if config and config.config.get("webhook_url"):
        return decrypt_api_key(config.config["webhook_url"])
    return None


async def run_actions(
    db_session,  # AsyncSession — imported inline to avoid circular deps
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message: str,
    bot_response: str,
    workspace_slack_webhook: str | None = None,
) -> list[dict[str, Any]]:
    """
    Check all enabled actions for the chatbot, fire matching ones, log events.
    Returns list of client-side payloads (for SSE emission, if applicable).
    """
    from app.services.action_service import list_enabled_actions

    actions = await list_enabled_actions(db_session, workspace_id, chatbot_id)
    if not actions:
        return []

    # Look up workspace Slack integration once for all slack_message actions
    slack_webhook = workspace_slack_webhook or await _get_workspace_slack_webhook(db_session, workspace_id)

    conversation_text = f"User: {user_message}\nAssistant: {bot_response}"
    context = {
        "conversation_id": str(conversation_id),
        "message": user_message,
        "response": bot_response,
    }

    internal_model = await get_internal_model(db_session, workspace_id)
    client_payloads: list[dict[str, Any]] = []

    for action in actions:
        triggered = await _ask_llm_trigger(conversation_text, action.trigger_description, model=internal_model)
        if not triggered:
            continue

        status, client_payload = await execute_action(action, context, slack_webhook)

        if client_payload:
            client_payloads.append(client_payload)

        event = ActionEvent(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            chatbot_id=chatbot_id,
            conversation_id=conversation_id,
            action_id=action.id,
            action_type=action.action_type,
            payload=context,
            status=status,
        )
        db_session.add(event)

    if actions:
        await db_session.flush()

    return client_payloads
