import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_config(session: AsyncSession, workspace_id: uuid.UUID, integration_type: str) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == integration_type,
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def create_issue(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    title: str,
    description: str,
    labels: list[str] | None = None,
) -> dict | None:
    jira_config = await _get_config(session, workspace_id, "jira")
    if jira_config:
        return await _create_jira_issue(jira_config, title, description, labels)

    linear_config = await _get_config(session, workspace_id, "linear")
    if linear_config:
        return await _create_linear_issue(linear_config, title, description, labels)

    return None


async def _create_jira_issue(
    config: dict,
    title: str,
    description: str,
    labels: list[str] | None = None,
) -> dict | None:
    try:
        from jira import JIRA

        jira = JIRA(
            server=config["server"],
            basic_auth=(config["email"], config["api_token"]),
        )

        issue_dict = {
            "project": {"key": config["project_key"]},
            "summary": title,
            "description": description,
            "issuetype": {"name": config.get("issue_type", "Task")},
        }
        if labels:
            issue_dict["labels"] = labels

        issue = jira.create_issue(fields=issue_dict)
        return {"key": issue.key, "url": f"{config['server']}/browse/{issue.key}"}
    except Exception:
        logger.error("Jira issue creation failed", exc_info=True)
        return None


async def _create_linear_issue(
    config: dict,
    title: str,
    description: str,
    labels: list[str] | None = None,
) -> dict | None:
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            mutation = """
            mutation IssueCreate($title: String!, $description: String, $teamId: String!) {
                issueCreate(input: {title: $title, description: $description, teamId: $teamId}) {
                    success
                    issue { id identifier url }
                }
            }
            """
            response = await client.post(
                "https://api.linear.app/graphql",
                headers={
                    "Authorization": config["api_token"],
                    "Content-Type": "application/json",
                },
                json={
                    "query": mutation,
                    "variables": {
                        "title": title,
                        "description": description,
                        "teamId": config["team_id"],
                    },
                },
            )
            data = response.json()
            issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
            if issue:
                return {"key": issue.get("identifier"), "url": issue.get("url")}
            return None
    except Exception:
        logger.error("Linear issue creation failed", exc_info=True)
        return None
