"""Workspace settings routes."""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organizational import Workspace, WorkspaceMembership, Agent
from app.models.integrations import IntegrationConfig

router = APIRouter(prefix="/settings")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    # Load team members
    members_result = await db.execute(
        select(Agent, WorkspaceMembership.role)
        .join(WorkspaceMembership, Agent.id == WorkspaceMembership.agent_id)
        .where(WorkspaceMembership.workspace_id == workspace.id)
    )
    members = [(agent, role) for agent, role in members_result.all()]

    # Load integrations
    int_result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.workspace_id == workspace.id)
    )
    integrations = int_result.scalars().all()

    return request.app.state.templates.TemplateResponse("settings/index.html", {
        "request": request, "workspace": workspace, "members": members, "integrations": integrations,
    })


@router.post("")
async def update_settings(
    request: Request, name: str = Form(None), timezone: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    if name:
        workspace.name = name
    if timezone:
        workspace.timezone = timezone
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Settings saved", "type": "success",
        })
    return RedirectResponse("/settings", status_code=303)


@router.get("/llm", response_class=HTMLResponse)
async def llm_settings(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    return request.app.state.templates.TemplateResponse("settings/llm.html", {
        "request": request, "workspace": workspace,
    })


@router.post("/llm")
async def update_llm_settings(
    request: Request, db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    form = await request.form()
    if "openrouter_api_key" in form and form["openrouter_api_key"]:
        from app.services.encryption import encrypt_api_key
        workspace.openrouter_api_key = encrypt_api_key(form["openrouter_api_key"])
    if "openrouter_base_url" in form:
        workspace.openrouter_base_url = form["openrouter_base_url"] or None
    if "internal_model" in form:
        workspace.internal_model = form["internal_model"] or None
    if "default_chatbot_model" in form:
        workspace.default_chatbot_model = form["default_chatbot_model"] or None
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "AI settings saved", "type": "success",
        })
    return RedirectResponse("/settings/llm", status_code=303)
