import json
import logging

from app.models.knowledge import Chatbot
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)

REFORMULATION_SYSTEM_PROMPT = (
    "You are a search query optimizer. Given a user question, generate 3 alternative phrasings "
    "that might match different content in a knowledge base. Return JSON only: "
    '{"queries": ["...", "...", "..."]}'
)


async def reformulate_queries(
    query: str,
    chatbot: Chatbot,
    openrouter_key: str | None = None,
    openrouter_base_url: str | None = None,
) -> list[str]:
    """Ask the LLM to rephrase the query 3 ways for better retrieval.

    Returns a list of rephrased queries, or an empty list on any error.
    """
    try:
        api_key = openrouter_key
        if api_key is None and chatbot.byoak:
            from app.services.encryption import decrypt_api_key
            api_key = decrypt_api_key(chatbot.byoak)

        provider = "openrouter" if openrouter_key else chatbot.llm_provider
        client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)

        response = await client.generate(
            messages=[
                {"role": "system", "content": REFORMULATION_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            model=chatbot.llm_model,
            temperature=0.7,
            max_tokens=200,
        )

        data = json.loads(response)
        queries = data.get("queries", [])
        if not isinstance(queries, list) or len(queries) == 0:
            logger.warning(f"Reformulation returned no queries for: {query[:80]}")
            return []
        return [q for q in queries if isinstance(q, str) and q.strip()]

    except Exception:
        logger.warning(f"Query reformulation failed for: {query[:80]}", exc_info=True)
        return []
