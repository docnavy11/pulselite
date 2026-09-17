"""Chatbot action routes."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot
from app.services.action_service import create_action, delete_action, list_actions

router = APIRouter()


@router.get("/chatbots/{chatbot_id}/actions", response_class=HTMLResponse)
async def actions_list(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    actions = await list_actions(db, workspace.id, chatbot_id)
    return request.app.state.templates.TemplateResponse(
        "chatbots/actions.html",
        {
            "request": request,
            "chatbot": chatbot,
            "actions": actions,
        },
    )


@router.post("/chatbots/{chatbot_id}/actions")
async def create_action_route(
    request: Request,
    chatbot_id: uuid.UUID,
    name: str = Form(...),
    action_type: str = Form(...),
    trigger_description: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    form = await request.form()
    config = {}
    if "url" in form:
        config["url"] = form["url"]
    if "webhook_url" in form:
        config["webhook_url"] = form["webhook_url"]
    if "message_template" in form:
        config["message_template"] = form["message_template"]
    if "calendly_url" in form:
        config["calendly_url"] = form["calendly_url"]

    action = await create_action(
        db,
        workspace.id,
        chatbot_id,
        action_type,
        name,
        trigger_description,
        config,
    )
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/action_row.html",
            {
                "request": request,
                "action": action,
                "chatbot_id": chatbot_id,
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/actions", status_code=303)


@router.post("/chatbots/{chatbot_id}/actions/{action_id}/toggle")
async def toggle_action(
    request: Request, chatbot_id: uuid.UUID, action_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    workspace = request.state.workspace
    from app.services.action_service import get_action

    action = await get_action(db, action_id, workspace.id)
    if action:
        action.is_enabled = not action.is_enabled
        await db.flush()
    return HTMLResponse("")


@router.delete("/chatbots/{chatbot_id}/actions/{action_id}")
async def delete_action_route(
    request: Request,
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    await delete_action(db, action_id, workspace.id)
    return HTMLResponse("")
