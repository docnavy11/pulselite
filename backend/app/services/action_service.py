import logging
import re
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionEvent, ChatbotAction
from app.models.integrations import IntegrationConfig
from app.services.encryption import decrypt_api_key
from app.services.web_search import search_web

logger = logging.getLogger(__name__)


async def list_actions(db: AsyncSession, chatbot_id: uuid.UUID, enabled_only: bool = True) -> list[ChatbotAction]:
    query = select(ChatbotAction).where(ChatbotAction.chatbot_id == chatbot_id)
    if enabled_only:
        query = query.where(ChatbotAction.is_enabled == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_action(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    data: dict,
) -> ChatbotAction:
    action = ChatbotAction(workspace_id=workspace_id, chatbot_id=chatbot_id, **data)
    db.add(action)
    await db.flush()
    return action


async def execute_action(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    action: ChatbotAction,
    arguments: dict,
) -> dict:
    event = ActionEvent(
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        conversation_id=conversation_id,
        action_id=action.id,
        action_type=action.action_type,
        payload=arguments,
        status="fired",
    )
    db.add(event)
    await db.flush()
    await db.commit()  # Commit event as "fired" before any external side effects

    if action.action_type == "webhook":
        url = action.config.get("url")
        if url and isinstance(url, str) and url.startswith("https://"):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(url, json={"action": action.name, **arguments})
                event.status = "completed"
            except Exception as e:
                logger.error(f"Webhook action failed: {e}")
                event.status = "failed"
        return {"type": "webhook", "name": action.name}

    elif action.action_type == "collect_lead":
        event.status = "completed"
        return {
            "type": "collect_lead",
            "name": action.name,
            "fields": action.config.get("fields", ["name", "email"]),
        }

    elif action.action_type == "custom_button":
        event.status = "completed"
        return {
            "type": "custom_button",
            "name": action.name,
            "label": action.config.get("label", action.name),
            "url": action.config.get("url", ""),
        }

    elif action.action_type in ("calendly", "calcom"):
        event.status = "completed"
        url = action.config.get("scheduling_url", "")
        label = action.config.get("label", "Book a meeting" if action.action_type == "calendly" else "Schedule a call")
        return {
            "type": action.action_type,
            "name": action.name,
            "label": label,
            "url": url,
        }

    elif action.action_type == "slack_message":
        webhook_url = action.config.get("webhook_url", "")
        if webhook_url and isinstance(webhook_url, str) and webhook_url.startswith("https://"):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    text = action.config.get("message_template", "New conversation from Pulse chat")
                    await client.post(webhook_url, json={"text": text})
                event.status = "completed"
            except Exception as e:
                logger.error(f"Slack action failed: {e}")
                event.status = "failed"
        return {"type": "slack_message", "name": action.name}

    elif action.action_type == "web_search":
        query = arguments.get("query", "") or action.config.get("default_query", "")
        if not query:
            event.status = "failed"
            return {"type": "web_search", "name": action.name, "results": "No query provided."}
        results = await search_web(query)
        event.status = "completed"
        return {
            "type": "web_search",
            "name": action.name,
            "results": results,
        }

    elif action.action_type == "shopify_order_status":
        shop_domain = action.config.get("shop_domain", "")

        # Extract order number from arguments or the last user message
        order_number = arguments.get("order_number", "")
        if not order_number:
            last_message = arguments.get("last_user_message", "")
            match = re.search(r"#?(\d{4,})", last_message)
            if match:
                order_number = match.group(1)

        if not order_number:
            event.status = "failed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": "I couldn't find an order number in your message. Please provide your order number (e.g. #1234).",
            }

        # Look up the Shopify IntegrationConfig for this workspace matching the shop domain
        integration_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.integration_type == "shopify",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        integration = integration_result.scalar_one_or_none()

        if not integration:
            event.status = "failed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": "Shopify integration is not connected for this workspace.",
            }

        cfg = integration.config or {}
        if shop_domain and cfg.get("shop") != shop_domain:
            event.status = "failed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": "Shopify shop domain mismatch — please check your action configuration.",
            }

        shop = cfg.get("shop", shop_domain)
        encrypted_token = cfg.get("access_token", "")
        try:
            access_token = decrypt_api_key(encrypted_token)
        except Exception as exc:
            logger.error(f"Failed to decrypt Shopify access token: {exc}")
            event.status = "failed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": "Unable to authenticate with Shopify. Please reconnect the integration.",
            }

        # Call Shopify Admin REST API
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://{shop}/admin/api/2024-01/orders.json",
                    headers={"X-Shopify-Access-Token": access_token},
                    params={"name": f"#{order_number}", "status": "any"},
                )
            if resp.status_code != 200:
                event.status = "failed"
                return {
                    "type": "shopify_order_status",
                    "name": action.name,
                    "result": f"Could not retrieve order information (HTTP {resp.status_code}).",
                }

            orders = resp.json().get("orders", [])
            if not orders:
                # Retry without # prefix in case the store uses numeric names only
                async with httpx.AsyncClient(timeout=10) as client:
                    resp2 = await client.get(
                        f"https://{shop}/admin/api/2024-01/orders.json",
                        headers={"X-Shopify-Access-Token": access_token},
                        params={"name": order_number, "status": "any"},
                    )
                orders = resp2.json().get("orders", []) if resp2.status_code == 200 else []

        except Exception as exc:
            logger.error(f"Shopify order lookup failed: {exc}")
            event.status = "failed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": "An error occurred while looking up your order. Please try again later.",
            }

        if not orders:
            event.status = "completed"
            return {
                "type": "shopify_order_status",
                "name": action.name,
                "result": f"No order found with number #{order_number}. Please double-check and try again.",
            }

        order = orders[0]
        status_label = (order.get("financial_status") or "unknown").replace("_", " ").title()
        fulfillment_label = (order.get("fulfillment_status") or "unfulfilled").replace("_", " ").title()
        total = order.get("total_price", "")
        currency = order.get("currency", "")

        # Collect tracking info from fulfillments
        tracking_lines = []
        for fulfillment in order.get("fulfillments", []):
            tracking_number = fulfillment.get("tracking_number")
            tracking_url = fulfillment.get("tracking_url")
            if tracking_number:
                line = f"Tracking: {tracking_number}"
                if tracking_url:
                    line += f" ({tracking_url})"
                tracking_lines.append(line)

        summary_parts = [
            f"Order #{order_number}",
            f"Payment: {status_label}",
            f"Fulfillment: {fulfillment_label}",
        ]
        if total and currency:
            summary_parts.append(f"Total: {currency} {total}")
        if tracking_lines:
            summary_parts.extend(tracking_lines)

        result_text = " | ".join(summary_parts)
        event.status = "completed"
        return {
            "type": "shopify_order_status",
            "name": action.name,
            "result": result_text,
        }

    elif action.action_type == "shopify_storefront":
        shop_url = action.config.get("shop_url", "")
        button_label = action.config.get("button_label", "Shop Now")
        event.status = "completed"
        # Return same shape as custom_button so the widget renders it identically
        return {
            "type": "custom_button",
            "name": action.name,
            "label": button_label,
            "url": shop_url,
        }

    elif action.action_type in ("stripe_get_invoices", "stripe_subscription_status"):
        # Resolve customer email from arguments or session data
        customer_email = (
            arguments.get("customer_email")
            or arguments.get("email")
            or (arguments.get("session_data") or {}).get("email")
            or ""
        )
        if not customer_email:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "I need the customer's email address to look up their Stripe account. Could you please provide it?",
            }

        # Fetch Stripe integration config for the workspace
        stripe_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.integration_type == "stripe",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        stripe_integration = stripe_result.scalar_one_or_none()

        if not stripe_integration:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Stripe integration is not connected for this workspace. Please configure it in Settings → Integrations.",
            }

        encrypted_key = (stripe_integration.config or {}).get("secret_key", "")
        try:
            stripe_key = decrypt_api_key(encrypted_key)
        except Exception as exc:
            logger.error(f"Failed to decrypt Stripe secret key: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Unable to authenticate with Stripe. Please reconnect the integration in Settings → Integrations.",
            }

        stripe_headers = {"Authorization": f"Bearer {stripe_key}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Step 1: Look up customer by email
                search_resp = await client.get(
                    "https://api.stripe.com/v1/customers/search",
                    headers=stripe_headers,
                    params={"query": f"email:'{customer_email}'", "limit": 1},
                )
            if search_resp.status_code != 200:
                event.status = "failed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": f"Stripe customer search failed (HTTP {search_resp.status_code}). Please try again later.",
                }

            customers = search_resp.json().get("data", [])
            if not customers:
                event.status = "completed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": f"No Stripe customer found with email {customer_email}.",
                }

            customer_id = customers[0]["id"]

            if action.action_type == "stripe_get_invoices":
                async with httpx.AsyncClient(timeout=10) as client:
                    inv_resp = await client.get(
                        "https://api.stripe.com/v1/invoices",
                        headers=stripe_headers,
                        params={"customer": customer_id, "limit": 5},
                    )
                if inv_resp.status_code != 200:
                    event.status = "failed"
                    return {
                        "type": action.action_type,
                        "name": action.name,
                        "result": f"Could not retrieve invoices (HTTP {inv_resp.status_code}).",
                    }

                invoices = inv_resp.json().get("data", [])
                if not invoices:
                    event.status = "completed"
                    return {
                        "type": action.action_type,
                        "name": action.name,
                        "result": f"No invoices found for {customer_email}.",
                    }

                lines = []
                for inv in invoices:
                    import datetime as _dt

                    amount = inv.get("amount_paid", inv.get("amount_due", 0))
                    currency = (inv.get("currency") or "usd").upper()
                    amount_fmt = f"{currency} {amount / 100:.2f}"
                    inv_status = (inv.get("status") or "unknown").title()
                    created_ts = inv.get("created") or 0
                    created_date = (
                        _dt.datetime.utcfromtimestamp(created_ts).strftime("%Y-%m-%d") if created_ts else "unknown date"
                    )
                    inv_url = inv.get("hosted_invoice_url", "")
                    line = f"• {created_date}: {amount_fmt} — {inv_status}"
                    if inv_url:
                        line += f" ({inv_url})"
                    lines.append(line)

                result_text = f"Recent invoices for {customer_email}:\n" + "\n".join(lines)
                event.status = "completed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": result_text,
                }

            else:  # stripe_subscription_status
                import datetime as _dt

                async with httpx.AsyncClient(timeout=10) as client:
                    sub_resp = await client.get(
                        "https://api.stripe.com/v1/subscriptions",
                        headers=stripe_headers,
                        params={"customer": customer_id, "status": "all", "limit": 3},
                    )
                if sub_resp.status_code != 200:
                    event.status = "failed"
                    return {
                        "type": action.action_type,
                        "name": action.name,
                        "result": f"Could not retrieve subscriptions (HTTP {sub_resp.status_code}).",
                    }

                subscriptions = sub_resp.json().get("data", [])
                if not subscriptions:
                    event.status = "completed"
                    return {
                        "type": action.action_type,
                        "name": action.name,
                        "result": f"No subscriptions found for {customer_email}.",
                    }

                lines = []
                for sub in subscriptions:
                    sub_status = (sub.get("status") or "unknown").title()
                    period_end_ts = sub.get("current_period_end") or 0
                    period_end = (
                        _dt.datetime.utcfromtimestamp(period_end_ts).strftime("%Y-%m-%d")
                        if period_end_ts
                        else "unknown"
                    )
                    cancel_at_end = sub.get("cancel_at_period_end", False)

                    # Try to get plan name from items
                    plan_name = "Unknown plan"
                    items = sub.get("items", {}).get("data", [])
                    if items:
                        price = items[0].get("price", {})
                        plan_name = (
                            price.get("nickname")
                            or (price.get("product") if isinstance(price.get("product"), str) else None)
                            or "Unknown plan"
                        )

                    line = f"• Plan: {plan_name} | Status: {sub_status} | Renews: {period_end}"
                    if cancel_at_end:
                        line += " (cancels at period end)"
                    lines.append(line)

                result_text = f"Subscription status for {customer_email}:\n" + "\n".join(lines)
                event.status = "completed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": result_text,
                }

        except Exception as exc:
            logger.error(f"Stripe action {action.action_type} failed: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "An error occurred while contacting Stripe. Please try again later.",
            }

    elif action.action_type == "salesforce_contact_lookup":
        email = arguments.get("email") or arguments.get("customer_email", "")
        if not email:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "I need an email address to look up the contact in Salesforce. Could you please provide it?",
            }

        sf_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.integration_type == "salesforce",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        sf_integration = sf_result.scalar_one_or_none()

        if not sf_integration:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Salesforce integration is not connected for this workspace. Please configure it in Settings → Integrations.",
            }

        cfg = sf_integration.config or {}
        instance_url = cfg.get("instance_url", "")
        encrypted_token = cfg.get("access_token", "")
        try:
            access_token = decrypt_api_key(encrypted_token)
        except Exception as exc:
            logger.error(f"Failed to decrypt Salesforce access token: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Unable to authenticate with Salesforce. Please reconnect the integration.",
            }

        # Sanitize email to prevent SOQL injection (strip single-quotes and backslashes)
        safe_email = email.replace("\\", "").replace("'", "\\'")
        soql = f"SELECT Id,Name,Email,Phone,Account.Name,LeadSource FROM Contact WHERE Email='{safe_email}' LIMIT 1"  # nosec B608

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{instance_url}/services/data/v58.0/query",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"q": soql},
                )
            if resp.status_code != 200:
                event.status = "failed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": f"Salesforce contact lookup failed (HTTP {resp.status_code}).",
                }

            records = resp.json().get("records", [])
            if not records:
                event.status = "completed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": f"No Salesforce contact found with email {email}.",
                }

            contact = records[0]
            name = contact.get("Name", "Unknown")
            phone = contact.get("Phone") or "N/A"
            account = (contact.get("Account") or {}).get("Name") or "N/A"
            lead_source = contact.get("LeadSource") or "N/A"

            result_text = (
                f"Salesforce Contact: {name} | Email: {email} | "
                f"Phone: {phone} | Company: {account} | Lead Source: {lead_source}"
            )
            event.status = "completed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": result_text,
            }

        except Exception as exc:
            logger.error(f"Salesforce contact lookup failed: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "An error occurred while contacting Salesforce. Please try again later.",
            }

    elif action.action_type == "salesforce_create_case":
        subject = arguments.get("subject", "")
        description = arguments.get("description", "")
        arguments.get("contact_email", "")

        subject_prefix = action.config.get("default_subject_prefix", "")
        if subject_prefix and not subject.startswith(subject_prefix):
            subject = f"{subject_prefix}{subject}"

        if not subject:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "A subject is required to create a Salesforce case.",
            }

        sf_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == workspace_id,
                IntegrationConfig.integration_type == "salesforce",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        sf_integration = sf_result.scalar_one_or_none()

        if not sf_integration:
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Salesforce integration is not connected for this workspace. Please configure it in Settings → Integrations.",
            }

        cfg = sf_integration.config or {}
        instance_url = cfg.get("instance_url", "")
        encrypted_token = cfg.get("access_token", "")
        try:
            access_token = decrypt_api_key(encrypted_token)
        except Exception as exc:
            logger.error(f"Failed to decrypt Salesforce access token: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "Unable to authenticate with Salesforce. Please reconnect the integration.",
            }

        case_body: dict = {
            "Subject": subject,
            "Description": description,
            "Status": "New",
            "Origin": "Chat",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{instance_url}/services/data/v58.0/sobjects/Case/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=case_body,
                )
            if resp.status_code not in (200, 201):
                event.status = "failed"
                return {
                    "type": action.action_type,
                    "name": action.name,
                    "result": f"Failed to create Salesforce case (HTTP {resp.status_code}).",
                }

            case_data = resp.json()
            case_id = case_data.get("id", "")

            # Try to fetch the case number for a friendlier response
            case_number = ""
            if case_id:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        num_resp = await client.get(
                            f"{instance_url}/services/data/v58.0/sobjects/Case/{case_id}",
                            headers={"Authorization": f"Bearer {access_token}"},
                            params={"fields": "CaseNumber"},
                        )
                    if num_resp.status_code == 200:
                        case_number = num_resp.json().get("CaseNumber", "")
                except Exception:
                    pass

            result_text = (
                f"Case #{case_number} created successfully in Salesforce."
                if case_number
                else f"Salesforce case created successfully (ID: {case_id})."
            )
            event.status = "completed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": result_text,
            }

        except Exception as exc:
            logger.error(f"Salesforce create case failed: {exc}")
            event.status = "failed"
            return {
                "type": action.action_type,
                "name": action.name,
                "result": "An error occurred while creating the Salesforce case. Please try again later.",
            }

    return {"type": action.action_type, "name": action.name}


def build_tools_for_chatbot(actions: list[ChatbotAction]) -> list[dict]:
    tools = []
    for action in actions:
        fn_name = f"action_{str(action.id).replace('-', '_')}"
        if action.action_type == "collect_lead":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why the lead form is being shown"},
                            },
                            "required": [],
                        },
                    },
                }
            )
        elif action.action_type == "webhook":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string", "description": "Why this action was triggered"},
                            },
                            "required": ["summary"],
                        },
                    },
                }
            )
        elif action.action_type == "web_search":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The search query to look up on the web"},
                            },
                            "required": ["query"],
                        },
                    },
                }
            )
        elif action.action_type in ("calendly", "calcom"):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }
            )
        elif action.action_type == "shopify_order_status":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "order_number": {
                                    "type": "string",
                                    "description": "The customer's order number (digits only, without the # prefix)",
                                },
                                "last_user_message": {
                                    "type": "string",
                                    "description": "The customer's last message, used to extract the order number if not provided explicitly",
                                },
                            },
                            "required": [],
                        },
                    },
                }
            )
        elif action.action_type == "shopify_storefront":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }
            )
        elif action.action_type in ("stripe_get_invoices", "stripe_subscription_status"):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "customer_email": {
                                    "type": "string",
                                    "description": "The customer's email address used to look them up in Stripe",
                                },
                            },
                            "required": ["customer_email"],
                        },
                    },
                }
            )
        elif action.action_type == "salesforce_contact_lookup":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "email": {
                                    "type": "string",
                                    "description": "The customer's email address used to look them up in Salesforce",
                                },
                            },
                            "required": ["email"],
                        },
                    },
                }
            )
        elif action.action_type == "salesforce_create_case":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action.trigger_description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "subject": {
                                    "type": "string",
                                    "description": "The subject/title of the support case to create",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "A detailed description of the issue for the support case",
                                },
                                "contact_email": {
                                    "type": "string",
                                    "description": "The customer's email address to associate with the case (optional)",
                                },
                            },
                            "required": ["subject", "description"],
                        },
                    },
                }
            )
    return tools
