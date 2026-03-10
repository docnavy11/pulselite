import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_linear_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "linear",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def create_linear_issue(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    title: str,
    description: str,
) -> bool:
    config = await _get_linear_config(session, workspace_id)
    if not config or not config.get("api_token"):
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Get teams
            team_query = """query { teams { nodes { id name } } }"""
            resp = await client.post(
                "https://api.linear.app/graphql",
                json={"query": team_query},
                headers={
                    "Authorization": config["api_token"],
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(f"Linear API error {resp.status_code}: {resp.text[:200]}")
                return False
            teams = resp.json().get("data", {}).get("teams", {}).get("nodes", [])
            if not teams:
                return False

            preferred = config.get("default_project", "")
            team_id = next(
                (t["id"] for t in teams if preferred and t["name"] == preferred),
                teams[0]["id"],
            )

            issue_mutation = """
            mutation CreateIssue($title: String!, $description: String, $teamId: String!) {
              issueCreate(input: {title: $title, description: $description, teamId: $teamId}) {
                success
              }
            }
            """
            mutation_resp = await client.post(
                "https://api.linear.app/graphql",
                json={
                    "query": issue_mutation,
                    "variables": {
                        "title": title,
                        "description": description,
                        "teamId": team_id,
                    },
                },
                headers={
                    "Authorization": config["api_token"],
                    "Content-Type": "application/json",
                },
            )
            result = mutation_resp.json()
            if not result.get("data", {}).get("issueCreate", {}).get("success"):
                logger.warning(f"Linear issue creation returned non-success: {result}")
                return False
            return True
    except Exception as e:
        logger.error(f"Linear issue creation failed: {e}")
        return False
