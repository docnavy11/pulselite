import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace, get_workspace_admin
from app.models.api_keys import ApiKey
from app.models.contacts import Company, Contact, ContactEvent, DataAttribute, Segment
from app.models.conversations import Conversation, ConversationTag, Message, Tag, Ticket
from app.models.intelligence import (
    AutonomousResolutionStats,
    ConversationAnalysis,
    GapCluster,
    GapEvent,
    IntelligenceSignal,
    LeadScore,
    RetrievalLog,
    TopicCluster,
)
from app.models.integrations import CreditLedger, IntegrationConfig
from app.models.actions import ActionEvent, ChatbotAction
from app.models.audit import AuditLog
from app.models.invites import WorkspaceInvite
from app.models.knowledge import Article, ArticleCollection, Chatbot, Chunk, Document, KnowledgeBase
from app.models.organizational import Agent, Inbox, Team, TeamMember, Workspace, WorkspaceMembership, WorkspaceWebhook
from app.models.sso import SSOConfig
from app.workers.tasks.gdpr_export import EXPORT_DIR, export_workspace_data

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["gdpr"])


@router.post("/export")
async def trigger_export(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    export_id = str(uuid.uuid4())
    export_workspace_data.delay(str(workspace_id), export_id)
    return {"export_id": export_id, "status": "processing"}


@router.get("/export/{export_id}/download")
async def download_export(
    export_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
):
    file_path = os.path.join(EXPORT_DIR, f"{str(export_id)}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found or still processing")
    return FileResponse(file_path, filename=f"pulse-export-{str(export_id)}.json", media_type="application/json")


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    await db.execute(delete(ContactEvent).where(ContactEvent.contact_id == contact_id))
    await db.execute(delete(LeadScore).where(LeadScore.contact_id == contact_id))
    await db.execute(delete(IntelligenceSignal).where(IntelligenceSignal.contact_id == contact_id))

    conv_result = await db.execute(select(Conversation.id).where(Conversation.contact_id == contact_id))
    conv_ids = [row[0] for row in conv_result.all()]
    if conv_ids:
        await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await db.execute(delete(ConversationTag).where(ConversationTag.conversation_id.in_(conv_ids)))
        await db.execute(delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conv_ids)))
        await db.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))

    await db.execute(delete(Contact).where(Contact.id == contact_id))
    await db.flush()

    return {"status": "deleted", "contact_id": str(contact_id)}


@router.delete("")
async def delete_workspace(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # Delete in FK-safe order

    # Chunks (depend on documents, knowledge_bases)
    await db.execute(delete(Chunk).where(Chunk.workspace_id == workspace_id))

    # Retrieval logs and gap events
    await db.execute(delete(GapEvent).where(GapEvent.workspace_id == workspace_id))
    await db.execute(delete(RetrievalLog).where(RetrievalLog.workspace_id == workspace_id))

    # Gap clusters
    await db.execute(delete(GapCluster).where(GapCluster.workspace_id == workspace_id))

    # Intelligence signals, lead scores, conversation analysis
    await db.execute(delete(IntelligenceSignal).where(IntelligenceSignal.workspace_id == workspace_id))
    await db.execute(delete(LeadScore).where(LeadScore.workspace_id == workspace_id))

    conv_result = await db.execute(select(Conversation.id).where(Conversation.workspace_id == workspace_id))
    conv_ids = [row[0] for row in conv_result.all()]
    if conv_ids:
        await db.execute(delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conv_ids)))
        await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await db.execute(delete(ConversationTag).where(ConversationTag.conversation_id.in_(conv_ids)))

    # Tickets, conversations
    await db.execute(delete(Ticket).where(Ticket.workspace_id == workspace_id))
    await db.execute(delete(Conversation).where(Conversation.workspace_id == workspace_id))

    # Documents, articles, article collections, knowledge bases
    await db.execute(delete(Document).where(Document.workspace_id == workspace_id))
    await db.execute(delete(Article).where(Article.workspace_id == workspace_id))
    await db.execute(delete(ArticleCollection).where(ArticleCollection.workspace_id == workspace_id))
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace_id))

    # Chatbot actions and events (depend on chatbots)
    await db.execute(delete(ActionEvent).where(ActionEvent.workspace_id == workspace_id))
    await db.execute(delete(ChatbotAction).where(ChatbotAction.workspace_id == workspace_id))

    # Chatbots, autonomous resolution stats, topic clusters
    await db.execute(delete(AutonomousResolutionStats).where(AutonomousResolutionStats.workspace_id == workspace_id))
    await db.execute(delete(TopicCluster).where(TopicCluster.workspace_id == workspace_id))
    await db.execute(delete(Chatbot).where(Chatbot.workspace_id == workspace_id))

    # API keys, integration configs, credit ledger
    await db.execute(delete(ApiKey).where(ApiKey.workspace_id == workspace_id))
    await db.execute(delete(IntegrationConfig).where(IntegrationConfig.workspace_id == workspace_id))
    await db.execute(delete(CreditLedger).where(CreditLedger.workspace_id == workspace_id))

    # Contacts, companies, contact events, data attributes, segments
    await db.execute(delete(ContactEvent).where(ContactEvent.workspace_id == workspace_id))
    await db.execute(delete(Contact).where(Contact.workspace_id == workspace_id))
    await db.execute(delete(Company).where(Company.workspace_id == workspace_id))
    await db.execute(delete(DataAttribute).where(DataAttribute.workspace_id == workspace_id))
    await db.execute(delete(Segment).where(Segment.workspace_id == workspace_id))

    # Tags
    await db.execute(delete(Tag).where(Tag.workspace_id == workspace_id))

    # Team members, teams, inboxes
    team_result = await db.execute(select(Team.id).where(Team.workspace_id == workspace_id))
    team_ids = [row[0] for row in team_result.all()]
    if team_ids:
        await db.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
    await db.execute(delete(Team).where(Team.workspace_id == workspace_id))
    await db.execute(delete(Inbox).where(Inbox.workspace_id == workspace_id))

    # Workspace invites, webhooks, SSO configs, audit logs
    await db.execute(delete(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace_id))
    await db.execute(delete(WorkspaceWebhook).where(WorkspaceWebhook.workspace_id == workspace_id))
    await db.execute(delete(SSOConfig).where(SSOConfig.workspace_id == workspace_id))
    await db.execute(delete(AuditLog).where(AuditLog.workspace_id == workspace_id))

    # Workspace memberships (delete this workspace's memberships first)
    await db.execute(delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id == workspace_id))

    # Agents whose home workspace is this one — reassign or delete
    from sqlalchemy import update as sa_update

    agent_result = await db.execute(select(Agent.id).where(Agent.workspace_id == workspace_id))
    agent_ids = [row[0] for row in agent_result.all()]
    if agent_ids:
        # For each agent, check if they have memberships in other workspaces
        still_member = await db.execute(
            select(WorkspaceMembership.agent_id, WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.agent_id.in_(agent_ids)
            )
        )
        # Build map: agent_id -> first other workspace_id
        agent_other_ws: dict = {}
        for row in still_member.all():
            if row[0] not in agent_other_ws:
                agent_other_ws[row[0]] = row[1]

        for aid in agent_ids:
            if aid in agent_other_ws:
                # Reassign home workspace to another workspace they belong to
                await db.execute(sa_update(Agent).where(Agent.id == aid).values(workspace_id=agent_other_ws[aid]))
            else:
                # Agent has no other workspace — safe to delete
                await db.execute(delete(TeamMember).where(TeamMember.agent_id == aid))
                await db.execute(delete(Agent).where(Agent.id == aid))

    # Workspace
    await db.delete(workspace)
    await db.flush()

    return {"status": "deleted", "workspace_id": str(workspace_id)}
