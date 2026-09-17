"""Workspace settings routes — all 9 sub-pages."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.integrations import IntegrationConfig
from app.models.invites import WorkspaceInvite
from app.models.organizational import Agent, Workspace, WorkspaceMembership

router = APIRouter(prefix="/settings")


# --- General ---

_COMMON_TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "America/Buenos_Aires",
    "America/Bogota",
    "America/Lima",
    "Europe/London",
    "Europe/Dublin",
    "Europe/Lisbon",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Europe/Brussels",
    "Europe/Zurich",
    "Europe/Stockholm",
    "Europe/Oslo",
    "Europe/Copenhagen",
    "Europe/Helsinki",
    "Europe/Warsaw",
    "Europe/Prague",
    "Europe/Vienna",
    "Europe/Budapest",
    "Europe/Bucharest",
    "Europe/Athens",
    "Europe/Istanbul",
    "Europe/Moscow",
    "Europe/Kiev",
    "Asia/Dubai",
    "Asia/Riyadh",
    "Asia/Kuwait",
    "Asia/Karachi",
    "Asia/Kolkata",
    "Asia/Colombo",
    "Asia/Dhaka",
    "Asia/Bangkok",
    "Asia/Jakarta",
    "Asia/Ho_Chi_Minh",
    "Asia/Singapore",
    "Asia/Kuala_Lumpur",
    "Asia/Manila",
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Taipei",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Brisbane",
    "Australia/Adelaide",
    "Australia/Perth",
    "Pacific/Auckland",
    "Pacific/Fiji",
    "Africa/Cairo",
    "Africa/Lagos",
    "Africa/Nairobi",
    "Africa/Johannesburg",
]


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_general(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    # Ensure current workspace timezone is in list
    tzs = list(_COMMON_TIMEZONES)
    if workspace.timezone and workspace.timezone not in tzs:
        tzs.insert(0, workspace.timezone)
    return request.app.state.templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "workspace": workspace,
            "timezones": tzs,
        },
    )


@router.post("")
async def update_general(
    request: Request, name: str = Form(None), timezone: str = Form(None), db: AsyncSession = Depends(get_db)
):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    updates = {}
    if name:
        updates["name"] = name
    if timezone:
        updates["timezone"] = timezone
    if updates:
        await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(**updates))
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Settings saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings", status_code=303)


@router.post("/export")
async def export_data(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from app.background.runner import submit_job

    await submit_job("gdpr_export", {"workspace_id": str(workspace.id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Export started. You'll be able to download it shortly.",
                "type": "success",
            },
        )
    return RedirectResponse("/settings", status_code=303)


@router.post("/delete-workspace")
async def delete_workspace(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    await db.delete(workspace)
    await db.commit()
    from app.services.auth_service import delete_session

    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(db, session_id)
        await db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_id")
    return response


# --- Team ---


@router.get("/team", response_class=HTMLResponse)
async def team_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    members_result = await db.execute(
        select(Agent, WorkspaceMembership.role)
        .join(WorkspaceMembership, Agent.id == WorkspaceMembership.agent_id)
        .where(WorkspaceMembership.workspace_id == workspace.id)
    )
    members = [(agent, role) for agent, role in members_result.all()]

    invites_result = await db.execute(
        select(WorkspaceInvite)
        .where(
            WorkspaceInvite.workspace_id == workspace.id,
        )
        .order_by(WorkspaceInvite.expires_at.desc())
    )
    invites = invites_result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        "settings/team.html",
        {
            "request": request,
            "members": members,
            "invites": invites,
        },
    )


@router.post("/team/invite")
async def send_invite(
    request: Request, email: str = Form(...), role: str = Form("member"), db: AsyncSession = Depends(get_db)
):
    workspace = request.state.workspace
    import secrets

    invite = WorkspaceInvite(
        workspace_id=workspace.id,
        email=email,
        role=role,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        invited_by_id=request.state.user.id,
    )
    db.add(invite)
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/invite_row.html",
            {
                "request": request,
                "invite": invite,
            },
        )
    return RedirectResponse("/settings/team", status_code=303)


@router.delete("/team/invite/{invite_id}")
async def revoke_invite(request: Request, invite_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    await db.execute(
        delete(WorkspaceInvite).where(WorkspaceInvite.id == invite_id, WorkspaceInvite.workspace_id == workspace.id)
    )
    return HTMLResponse("")


# --- Billing ---


@router.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from app.services.credits import get_balance, get_history
    from app.services.deployment import is_cloud

    cloud_mode = is_cloud()
    balance = await get_balance(db, workspace.id) if cloud_mode else 0
    history = await get_history(db, workspace.id, limit=20) if cloud_mode else []
    return request.app.state.templates.TemplateResponse(
        "settings/billing.html",
        {
            "request": request,
            "cloud_mode": cloud_mode,
            "balance": balance,
            "history": history,
            "workspace": workspace,
        },
    )


@router.post("/billing/auto-recharge")
async def update_auto_recharge(request: Request, db: AsyncSession = Depends(get_db)):
    from app.services.deployment import is_cloud

    if not is_cloud():
        return HTMLResponse("Not available", status_code=404)
    workspace = request.state.workspace
    form = await request.form()
    from sqlalchemy import update as sa_update

    try:
        threshold = int(form.get("auto_recharge_threshold", 200))
        amount = int(form.get("auto_recharge_amount", 1000))
    except (ValueError, TypeError):
        threshold, amount = 200, 1000
    await db.execute(
        sa_update(Workspace)
        .where(Workspace.id == workspace.id)
        .values(
            auto_recharge_enabled="auto_recharge_enabled" in form,
            auto_recharge_threshold=threshold,
            auto_recharge_amount=amount,
        )
    )
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Auto-recharge settings saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/billing", status_code=303)


@router.post("/billing/checkout")
async def checkout(request: Request, db: AsyncSession = Depends(get_db)):
    from app.services.deployment import is_cloud

    if not is_cloud():
        return HTMLResponse("Not available", status_code=404)
    workspace = request.state.workspace
    from app.services.billing import create_checkout_session

    url = await create_checkout_session(db, workspace)
    return RedirectResponse(url, status_code=303)


@router.post("/billing/portal")
async def portal(request: Request, db: AsyncSession = Depends(get_db)):
    from app.services.deployment import is_cloud

    if not is_cloud():
        return HTMLResponse("Not available", status_code=404)
    workspace = request.state.workspace
    from app.services.billing import create_portal_session

    url = await create_portal_session(db, workspace)
    return RedirectResponse(url, status_code=303)


# --- Integrations ---


@router.get("/integrations", response_class=HTMLResponse)
async def integrations_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.workspace_id == workspace.id))
    configs = {ic.integration_type: ic for ic in result.scalars().all()}
    return request.app.state.templates.TemplateResponse(
        "settings/integrations.html",
        {
            "request": request,
            "configs": configs,
        },
    )


_VALID_INTEGRATION_TYPES = {
    "slack",
    "slack_bot",
    "email",
    "hubspot",
    "jira",
    "linear",
    "notion",
    "whatsapp",
    "messenger",
    "instagram",
    "shopify",
    "google_drive",
    "zendesk",
    "stripe",
    "salesforce",
    "dropbox",
}

_SENSITIVE_FIELDS = {
    "webhook_url",
    "api_key",
    "access_token",
    "api_token",
    "secret_key",
    "password",
    "page_access_token",
}


@router.post("/integrations/{integration_type}")
async def save_integration(request: Request, integration_type: str, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    if integration_type not in _VALID_INTEGRATION_TYPES:
        return HTMLResponse("Invalid integration type", status_code=400)

    form = await request.form()
    new_config = {k: v for k, v in form.items() if v}

    # Encrypt sensitive fields
    if getattr(settings, "FERNET_KEY", None):
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            for key in _SENSITIVE_FIELDS:
                if key in new_config and new_config[key]:
                    new_config[key] = f.encrypt(new_config[key].encode()).decode()
        except Exception:
            pass

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace.id,
            IntegrationConfig.integration_type == integration_type,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Merge: keep old sensitive values if not re-submitted
        merged = dict(existing.config or {})
        merged.update(new_config)
        existing.config = merged
        existing.is_active = True
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(existing, "config")
    else:
        db.add(
            IntegrationConfig(
                workspace_id=workspace.id,
                integration_type=integration_type,
                config=new_config,
                is_active=True,
            )
        )
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": f"{integration_type.replace('_', ' ').title()} settings saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/integrations", status_code=303)


@router.delete("/integrations/{integration_type}")
async def disconnect_integration(request: Request, integration_type: str, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace.id,
            IntegrationConfig.integration_type == integration_type,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.is_active = False
        await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": f"{integration_type.replace('_', ' ').title()} disconnected",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/integrations", status_code=303)


# --- AI Models ---


def _llm_template_ctx(request, workspace):
    """Shared context for the LLM settings page."""
    from app.config import settings as app_settings
    from app.services.deployment import is_cloud

    return {
        "request": request,
        "workspace": workspace,
        "cloud_mode": is_cloud(),
        "env_api_key_set": bool(getattr(app_settings, "AI_API_KEY", None)),
        "env_base_url": getattr(app_settings, "AI_BASE_URL", None),
        "env_default_chatbot_model": getattr(app_settings, "DEFAULT_CHATBOT_MODEL", None),
        "env_internal_model": getattr(app_settings, "INTERNAL_MODEL", None),
    }


@router.get("/llm", response_class=HTMLResponse)
async def llm_settings(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    return request.app.state.templates.TemplateResponse("settings/llm.html", _llm_template_ctx(request, workspace))


@router.post("/llm/byok")
async def toggle_byok(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    new_byok = not getattr(workspace, "is_byok", False)
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(is_byok=new_byok))
    workspace.is_byok = new_byok
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("settings/llm.html", _llm_template_ctx(request, workspace))
    return RedirectResponse("/settings/llm", status_code=303)


@router.post("/llm/key")
async def save_llm_key(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    form = await request.form()
    key = form.get("openrouter_api_key", "").strip()
    if key:
        from sqlalchemy import update as sa_update

        from app.services.encryption import encrypt_api_key

        encrypted = encrypt_api_key(key)
        await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(openrouter_api_key=encrypted))
        workspace.openrouter_api_key = encrypted
    if request.headers.get("HX-Request"):
        msg = "API key saved" if key else "No key provided"
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": msg,
                "type": "success" if key else "error",
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


@router.post("/llm/key/remove")
async def remove_llm_key(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(openrouter_api_key=None))
    workspace.openrouter_api_key = None
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "API key removed",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


@router.post("/llm/base-url")
async def save_base_url(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    form = await request.form()
    from sqlalchemy import update as sa_update

    val = form.get("openrouter_base_url", "").strip() or None
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(openrouter_base_url=val))
    workspace.openrouter_base_url = val
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Base URL saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


@router.get("/llm/models", response_class=HTMLResponse)
async def load_openrouter_models(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from app.config import settings as app_settings
    from app.services.encryption import decrypt_api_key

    api_key = None
    if workspace.openrouter_api_key:
        try:
            api_key = decrypt_api_key(workspace.openrouter_api_key)
        except Exception:
            pass
    if not api_key:
        api_key = getattr(app_settings, "AI_API_KEY", None)

    if not api_key:
        return request.app.state.templates.TemplateResponse(
            "settings/_llm_models.html",
            {
                "request": request,
                "error": "No API key configured. Save your key first.",
                "models": [],
                "selected_models": [],
            },
        )

    raw_base = (
        workspace.openrouter_base_url or getattr(app_settings, "AI_BASE_URL", None) or "https://openrouter.ai/api/v1"
    )
    from urllib.parse import urlparse

    parsed = urlparse(raw_base)
    if parsed.scheme not in ("http", "https"):
        return request.app.state.templates.TemplateResponse(
            "settings/_llm_models.html",
            {
                "request": request,
                "error": "Invalid base URL scheme.",
                "models": [],
                "selected_models": [],
            },
        )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{raw_base.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        data = resp.json()
        models = [
            {"id": m["id"], "name": m.get("name", m["id"]), "context_length": m.get("context_length")}
            for m in data.get("data", [])
            if "embedding" not in m["id"]
        ]
    except Exception as e:
        return request.app.state.templates.TemplateResponse(
            "settings/_llm_models.html",
            {
                "request": request,
                "error": f"Failed to load models — ensure your API key is valid. ({e})",
                "models": [],
                "selected_models": [],
            },
        )

    return request.app.state.templates.TemplateResponse(
        "settings/_llm_models.html",
        {
            "request": request,
            "models": models,
            "selected_models": workspace.allowed_models or [],
        },
    )


@router.post("/llm/models")
async def save_llm_models(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    form = await request.form()
    import json as _json

    from sqlalchemy import update as sa_update

    try:
        allowed = _json.loads(form.get("allowed_models", "[]"))
        if not isinstance(allowed, list):
            allowed = []
    except (ValueError, TypeError):
        allowed = []
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(allowed_models=allowed))
    # Keep in-memory object in sync for the response template
    workspace.allowed_models = allowed
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "settings/_llm_models_saved.html",
            {
                **_llm_template_ctx(request, workspace),
                "workspace": workspace,
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


@router.post("/llm/default-chatbot-model")
async def save_default_chatbot_model(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    form = await request.form()
    from sqlalchemy import update as sa_update

    val = form.get("default_chatbot_model", "").strip() or None
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(default_chatbot_model=val))
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Default chatbot model saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


@router.post("/llm/internal-model")
async def save_internal_model(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    form = await request.form()
    from sqlalchemy import update as sa_update

    val = form.get("internal_model", "").strip() or None
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(internal_model=val))
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Background tasks model saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/llm", status_code=303)


# --- Security ---


@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = request.state.user
    return request.app.state.templates.TemplateResponse(
        "settings/security.html",
        {
            "request": request,
            "twofa_enabled": user.two_fa_enabled,
            "setup_uri": None,
            "setup_secret": None,
        },
    )


@router.post("/security/2fa/setup")
async def setup_2fa(request: Request, db: AsyncSession = Depends(get_db)):
    user = request.state.user
    import pyotp

    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.flush()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Pulse Lite")
    return request.app.state.templates.TemplateResponse(
        "settings/security.html",
        {
            "request": request,
            "twofa_enabled": False,
            "setup_uri": uri,
            "setup_secret": secret,
        },
    )


@router.post("/security/2fa/verify")
async def verify_2fa(request: Request, code: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = request.state.user
    import pyotp

    if not user.totp_secret:
        return HTMLResponse("Setup not started", status_code=400)
    totp = pyotp.TOTP(user.totp_secret)
    if totp.verify(code):
        user.two_fa_enabled = True
        await db.flush()
        if request.headers.get("HX-Request"):
            return request.app.state.templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "message": "2FA enabled successfully",
                    "type": "success",
                },
            )
    else:
        if request.headers.get("HX-Request"):
            return request.app.state.templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "message": "Invalid code",
                    "type": "error",
                },
            )
    return RedirectResponse("/settings/security", status_code=303)


@router.post("/security/2fa/disable")
async def disable_2fa(request: Request, code: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = request.state.user
    import pyotp

    if user.totp_secret and pyotp.TOTP(user.totp_secret).verify(code):
        user.two_fa_enabled = False
        user.totp_secret = None
        await db.flush()
        if request.headers.get("HX-Request"):
            return request.app.state.templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "message": "2FA disabled",
                    "type": "success",
                },
            )
    else:
        if request.headers.get("HX-Request"):
            return request.app.state.templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "message": "Invalid code",
                    "type": "error",
                },
            )
    return RedirectResponse("/settings/security", status_code=303)


# --- Data Retention ---


@router.get("/data-retention", response_class=HTMLResponse)
async def data_retention_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    return request.app.state.templates.TemplateResponse(
        "settings/data_retention.html",
        {
            "request": request,
            "workspace": workspace,
        },
    )


@router.post("/data-retention")
async def update_data_retention(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    form = await request.form()
    retention_days = form.get("retention_days", "")
    if retention_days == "custom":
        custom_val = form.get("retention_days_custom", "")
        val = int(custom_val) if custom_val and custom_val.isdigit() else None
    else:
        val = int(retention_days) if retention_days else None
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(data_retention_days=val))
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Retention policy saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/data-retention", status_code=303)


# --- Webhooks ---


@router.get("/webhooks", response_class=HTMLResponse)
async def webhooks_page(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.organizational import WorkspaceWebhook

    workspace = request.state.workspace
    webhooks = (
        (await db.execute(select(WorkspaceWebhook).where(WorkspaceWebhook.workspace_id == workspace.id)))
        .scalars()
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        "settings/webhooks.html",
        {
            "request": request,
            "webhooks": webhooks,
        },
    )


@router.post("/webhooks")
async def create_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.organizational import WorkspaceWebhook

    workspace = request.state.workspace
    form = await request.form()
    url = form.get("url", "")
    # event_types submitted as multiple checkboxes with the same name
    events = form.getlist("event_types")
    if not events:
        events = ["conversation.created", "conversation.escalated"]
    secret = form.get("secret") or None
    webhook = WorkspaceWebhook(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        url=url,
        event_types=events,
        secret=secret,
    )
    db.add(webhook)
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/webhook_row.html",
            {
                "request": request,
                "webhook": webhook,
            },
        )
    return RedirectResponse("/settings/webhooks", status_code=303)


@router.put("/webhooks/{webhook_id}")
async def update_webhook(request: Request, webhook_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update as sa_update

    from app.models.organizational import WorkspaceWebhook

    workspace = request.state.workspace
    form = await request.form()
    url = form.get("url", "")
    events = form.getlist("event_types")
    if not events:
        events = ["conversation.created", "conversation.escalated"]
    secret_input = form.get("secret") or None
    values: dict = {"url": url, "event_types": events}
    if secret_input:
        values["secret"] = secret_input
    await db.execute(
        sa_update(WorkspaceWebhook)
        .where(WorkspaceWebhook.id == webhook_id, WorkspaceWebhook.workspace_id == workspace.id)
        .values(**values)
    )
    result = await db.execute(select(WorkspaceWebhook).where(WorkspaceWebhook.id == webhook_id))
    webhook = result.scalar_one()
    return request.app.state.templates.TemplateResponse(
        "components/webhook_row.html",
        {
            "request": request,
            "webhook": webhook,
        },
    )


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(request: Request, webhook_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.organizational import WorkspaceWebhook

    workspace = request.state.workspace
    result = await db.execute(
        select(WorkspaceWebhook).where(WorkspaceWebhook.id == webhook_id, WorkspaceWebhook.workspace_id == workspace.id)
    )
    webhook = result.scalar_one_or_none()
    if webhook:
        await db.delete(webhook)
        await db.flush()
    return HTMLResponse("")


@router.get("/webhooks/{webhook_id}/deliveries/partial", response_class=HTMLResponse)
async def webhook_deliveries_partial(request: Request, webhook_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.webhook_delivery import WebhookDelivery

    workspace = request.state.workspace
    deliveries = (
        (
            await db.execute(
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.webhook_id == webhook_id,
                    WebhookDelivery.workspace_id == workspace.id,
                )
                .order_by(WebhookDelivery.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        "settings/_webhook_deliveries_partial.html",
        {
            "request": request,
            "deliveries": deliveries,
        },
    )


@router.get("/webhooks/{webhook_id}/deliveries", response_class=HTMLResponse)
async def webhook_deliveries(request: Request, webhook_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.webhook_delivery import WebhookDelivery

    workspace = request.state.workspace
    deliveries = (
        (
            await db.execute(
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.webhook_id == webhook_id,
                    WebhookDelivery.workspace_id == workspace.id,
                )
                .order_by(WebhookDelivery.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        "settings/webhook_deliveries.html",
        {
            "request": request,
            "deliveries": deliveries,
            "webhook_id": webhook_id,
        },
    )


# --- Intelligence Config ---


@router.get("/intelligence", response_class=HTMLResponse)
async def intelligence_config_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    return request.app.state.templates.TemplateResponse(
        "settings/intelligence_config.html",
        {
            "request": request,
            "intelligence_config": workspace.intelligence_config or {},
        },
    )


@router.post("/intelligence/toggle/{key}")
async def toggle_intelligence(request: Request, key: str, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    config = dict(workspace.intelligence_config or {})
    config[key] = not config.get(key, True)
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(intelligence_config=config))
    if request.headers.get("HX-Request"):
        task_meta = {
            "auto_analyze": {
                "name": "Conversation Analysis",
                "desc": "Automatically analyze conversations for sentiment, intent, and topics when they close.",
                "schedule": "On conversation close",
            },
            "sentiment_trends": {
                "name": "Sentiment Trends",
                "desc": "Compute daily sentiment averages across all conversations.",
                "schedule": "Daily at 4:00 AM",
            },
            "gap_clustering": {
                "name": "Gap Clustering",
                "desc": "Cluster unanswered questions into topic groups using BERTopic.",
                "schedule": "Daily at 3:00 AM",
            },
        }
        meta = task_meta.get(key, {"name": key, "desc": "", "schedule": ""})
        enabled = config[key]
        badge_cls = "bg-green-100 text-green-700" if enabled else "bg-gray-100 text-gray-500"
        badge_text = "Active" if enabled else "Disabled"
        btn_text = "Disable" if enabled else "Enable"
        html = f"""<div id="intel-task-{key}" class="bg-white rounded-xl border border-warm-200 p-5">
    <div class="flex items-center justify-between">
        <div>
            <h3 class="text-sm font-semibold text-gray-900">{meta["name"]}</h3>
            <p class="text-xs text-gray-500 mt-0.5">{meta["desc"]}</p>
            <p class="text-xs text-gray-400 mt-1">Schedule: {meta["schedule"]}</p>
        </div>
        <div class="flex items-center gap-3">
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium {badge_cls}">{badge_text}</span>
            <form hx-post="/settings/intelligence/toggle/{key}" hx-target="#intel-task-{key}" hx-swap="outerHTML">
                <button type="submit" class="text-xs text-brand-600 hover:text-brand-700 font-medium">{btn_text}</button>
            </form>
        </div>
    </div>
</div>"""
        return HTMLResponse(html)
    return RedirectResponse("/settings/intelligence", status_code=303)


@router.post("/intelligence/reports")
async def update_reports(
    request: Request,
    report_frequency: str = Form("off"),
    report_recipients: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    from sqlalchemy import update as sa_update

    config = dict(workspace.intelligence_config or {})
    config["report_frequency"] = report_frequency
    config["report_recipients"] = report_recipients
    await db.execute(sa_update(Workspace).where(Workspace.id == workspace.id).values(intelligence_config=config))
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Report settings saved",
                "type": "success",
            },
        )
    return RedirectResponse("/settings/intelligence", status_code=303)
