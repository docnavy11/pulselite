"""Q&A pair management routes."""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot
from app.models.qa import QAPair

router = APIRouter()


@router.get("/chatbots/{chatbot_id}/qa", response_class=HTMLResponse)
async def qa_list(request: Request, chatbot_id: uuid.UUID, status: str | None = None, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)

    query = select(QAPair).where(QAPair.chatbot_id == chatbot_id, QAPair.workspace_id == workspace.id)
    if status:
        query = query.where(QAPair.status == status)
    query = query.order_by(QAPair.created_at.desc())
    pairs = (await db.execute(query)).scalars().all()

    return request.app.state.templates.TemplateResponse("chatbots/qa.html", {
        "request": request, "chatbot": chatbot, "pairs": pairs, "status_filter": status,
    })


@router.post("/chatbots/{chatbot_id}/qa/generate")
async def generate_qa(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    from app.background.runner import submit_job
    await submit_job("generate_qa", {"chatbot_id": str(chatbot_id), "workspace_id": str(workspace.id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Generating Q&A pairs...", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}/qa", status_code=303)


@router.post("/chatbots/{chatbot_id}/qa/run-tests")
async def run_all_tests(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    await db.execute(
        update(QAPair).where(QAPair.chatbot_id == chatbot_id, QAPair.workspace_id == workspace.id)
        .values(status="pending")
    )
    await db.flush()
    pairs = (await db.execute(
        select(QAPair.id).where(QAPair.chatbot_id == chatbot_id, QAPair.workspace_id == workspace.id)
    )).scalars().all()
    from app.background.runner import submit_job
    for qa_id in pairs:
        await submit_job("test_qa_question", {"qa_id": str(qa_id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": f"Queued {len(pairs)} Q&A pairs for testing", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}/qa", status_code=303)


@router.post("/chatbots/{chatbot_id}/qa/{qa_id}/suggest")
async def suggest_answer(request: Request, chatbot_id: uuid.UUID, qa_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(QAPair).where(QAPair.id == qa_id, QAPair.workspace_id == workspace.id))
    pair = result.scalar_one_or_none()
    if pair:
        from app.background.runner import submit_job
        await submit_job("suggest_qa_answer", {"qa_id": str(qa_id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Generating AI suggestion...", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}/qa", status_code=303)


@router.post("/chatbots/{chatbot_id}/qa")
async def create_qa(
    request: Request, chatbot_id: uuid.UUID,
    question: str = Form(...), answer: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    qa = QAPair(workspace_id=workspace.id, chatbot_id=chatbot_id, question=question, answer=answer, status="pending")
    db.add(qa)
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/qa_row.html", {
            "request": request, "pair": qa,
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}/qa", status_code=303)


@router.delete("/chatbots/{chatbot_id}/qa/{qa_id}")
async def delete_qa(request: Request, chatbot_id: uuid.UUID, qa_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(QAPair).where(QAPair.id == qa_id, QAPair.workspace_id == workspace.id))
    pair = result.scalar_one_or_none()
    if pair:
        await db.delete(pair)
        await db.flush()
    return HTMLResponse("")


@router.post("/chatbots/{chatbot_id}/qa/{qa_id}/retest")
async def retest_qa(request: Request, chatbot_id: uuid.UUID, qa_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(QAPair).where(QAPair.id == qa_id, QAPair.workspace_id == workspace.id))
    pair = result.scalar_one_or_none()
    if pair:
        pair.status = "pending"
        await db.flush()
        from app.background.runner import submit_job
        await submit_job("test_qa_question", {"qa_id": str(qa_id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Retesting...", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}/qa", status_code=303)
