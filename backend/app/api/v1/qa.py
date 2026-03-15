import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.schemas.qa import CreateQAPairRequest, GenerateQARequest, QAPairListResponse, QAPairResponse, QAPairUpdate
from app.services.chatbot_service import get_chatbot
from app.services.qa_service import (
    add_qa_to_kb,
    count_qa_pairs,
    create_qa_pair,
    delete_qa_pair,
    get_qa_pair,
    get_pending_pair_ids,
    get_testable_pair_ids,
    has_pending_pairs,
    list_qa_pairs,
    reset_pairs_for_retest,
    update_qa_pair,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/chatbots/{chatbot_id}/qa",
    tags=["qa"],
)


@router.get("", response_model=QAPairListResponse)
async def list_pairs(
    chatbot_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_qa_pairs(
        db, workspace_id=workspace_id, chatbot_id=chatbot_id,
        page=page, page_size=page_size, status_filter=status_filter,
    )
    return QAPairListResponse(items=items, total=total)


@router.post("/generate", status_code=202)
async def generate(
    chatbot_id: uuid.UUID,
    body: GenerateQARequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await get_chatbot(db, workspace_id, chatbot_id)

    if await has_pending_pairs(db, chatbot_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A generation job is already in progress for this chatbot",
        )

    current_count = await count_qa_pairs(db, chatbot_id)
    if current_count + body.count > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Would exceed 200 QA pair limit. Currently {current_count}, requested {body.count}.",
        )

    from app.workers.tasks.generate_qa import generate_qa
    generate_qa.delay(str(chatbot_id), str(workspace_id), body.count)

    return {"status": "queued", "count": body.count}


@router.post("", response_model=QAPairResponse, status_code=201)
async def create_pair(
    chatbot_id: uuid.UUID,
    body: CreateQAPairRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await get_chatbot(db, workspace_id, chatbot_id)

    current_count = await count_qa_pairs(db, chatbot_id)
    if current_count >= 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="200 QA pair limit reached.",
        )

    pair = await create_qa_pair(db, workspace_id, chatbot_id, body.question)
    await db.commit()
    return pair


@router.post("/run-tests", status_code=202)
async def run_tests(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch test tasks for all pending QA pairs."""
    await get_chatbot(db, workspace_id, chatbot_id)

    pair_ids = await get_pending_pair_ids(db, chatbot_id)
    if not pair_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending questions to test.",
        )

    from app.workers.tasks.generate_qa import test_qa_question
    for pid in pair_ids:
        test_qa_question.delay(str(pid))

    return {"status": "queued", "count": len(pair_ids)}


@router.post("/retest-all", status_code=202)
async def retest_all(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Reset all completed/failed pairs to pending and dispatch test tasks."""
    await get_chatbot(db, workspace_id, chatbot_id)

    pair_ids = await get_testable_pair_ids(db, chatbot_id)
    if not pair_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No questions to re-test.",
        )

    # Reset all to testing
    await reset_pairs_for_retest(db, chatbot_id, pair_ids)
    await db.commit()

    from app.workers.tasks.generate_qa import test_qa_question
    for pid in pair_ids:
        test_qa_question.delay(str(pid))

    return {"status": "queued", "count": len(pair_ids)}


@router.put("/{qa_pair_id}", response_model=QAPairResponse)
async def update_pair(
    qa_pair_id: uuid.UUID,
    body: QAPairUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    kwargs = body.model_dump(exclude_unset=True)
    pair = await update_qa_pair(db, workspace_id=workspace_id, qa_pair_id=qa_pair_id, **kwargs)
    return pair


@router.delete("/{qa_pair_id}", status_code=204)
async def delete_pair(
    qa_pair_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await delete_qa_pair(db, workspace_id=workspace_id, qa_pair_id=qa_pair_id)


@router.post("/{qa_pair_id}/suggest", status_code=202)
async def suggest_answer(
    qa_pair_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    pair = await get_qa_pair(db, workspace_id, qa_pair_id)

    from app.workers.tasks.generate_qa import suggest_qa_answer
    suggest_qa_answer.delay(str(pair.id), str(workspace_id))

    return {"status": "queued"}


@router.post("/{qa_pair_id}/retest", status_code=202)
async def retest_pair(
    qa_pair_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    pair = await get_qa_pair(db, workspace_id, qa_pair_id)
    pair.status = "testing"
    pair.answer = None
    pair.confidence_score = None
    pair.escalated = False
    pair.error_message = None
    await db.commit()  # Commit BEFORE dispatching Celery task

    from app.workers.tasks.generate_qa import test_qa_question
    test_qa_question.delay(str(pair.id))

    return {"status": "queued"}


@router.post("/{qa_pair_id}/add-to-kb", status_code=201)
async def add_pair_to_kb(
    qa_pair_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    pair = await get_qa_pair(db, workspace_id, qa_pair_id)

    if pair.kb_document_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already added to KB")
    if not pair.answer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answer to add")

    doc = await add_qa_to_kb(db, pair, chatbot_id, workspace_id)
    return {"status": "ok", "document_id": str(doc.id)}
