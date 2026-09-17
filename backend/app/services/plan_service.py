"""Cached plan tier lookups."""

import logging

from app.services.deployment import is_self_hosted

logger = logging.getLogger(__name__)

# In-memory cache, loaded at startup via load_plan_tiers()
_tier_cache: dict = {}


async def load_plan_tiers() -> None:
    """Load all plan tiers from DB into memory. Call once at app startup."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.plan_tier import PlanTier

    async with async_session_factory() as session:
        result = await session.execute(select(PlanTier))
        tiers = result.scalars().all()
        _tier_cache.clear()
        for tier in tiers:
            _tier_cache[tier.slug] = tier
        logger.info(f"Loaded {len(_tier_cache)} plan tiers")


def get_plan_tier(slug: str):
    """Return PlanTier for slug, falling back to enterprise for unknown slugs."""
    return _tier_cache.get(slug, _tier_cache.get("enterprise"))


def get_plan_limits(slug: str) -> dict:
    """Return limits dict for a plan slug."""
    tier = get_plan_tier(slug)
    if tier is None:
        return {"chatbots": -1, "conversations": -1, "knowledge_bases": -1, "chars_indexed": -1}
    return {
        "chatbots": tier.max_chatbots,
        "conversations": tier.max_conversations_monthly,
        "knowledge_bases": tier.max_knowledge_bases,
        "chars_indexed": tier.max_chars_indexed,
    }


def has_feature(workspace, feature: str) -> bool:
    """Check if workspace's plan includes a feature. Always True in self-hosted mode."""
    if is_self_hosted():
        return True
    tier = get_plan_tier(workspace.plan)
    if tier is None:
        return True
    return feature in (tier.features or [])


def get_all_tiers() -> list:
    """Return all cached plan tiers. Used by billing plans endpoint."""
    return list(_tier_cache.values())
