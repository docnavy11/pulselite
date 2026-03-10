"""DuckDuckGo Instant Answer search — free, no API key required."""

import httpx


async def search_web(query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo and return a formatted string of results for LLM context."""
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
        "no_redirect": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return f"Web search unavailable for: {query}"

    lines: list[str] = []

    # Abstract (main answer)
    if data.get("Abstract"):
        lines.append(f"Summary: {data['Abstract']}")
        if data.get("AbstractURL"):
            lines.append(f"Source: {data['AbstractURL']}")

    # Instant answer
    if data.get("Answer"):
        lines.append(f"Answer: {data['Answer']}")

    # Related topics (top N)
    topics = data.get("RelatedTopics", [])
    count = 0
    for topic in topics:
        if count >= max_results:
            break
        # Topics can be nested groups
        if "Topics" in topic:
            for sub in topic["Topics"]:
                if count >= max_results:
                    break
                text = sub.get("Text", "")
                if text:
                    lines.append(f"- {text}")
                    count += 1
        else:
            text = topic.get("Text", "")
            if text:
                lines.append(f"- {text}")
                count += 1

    if not lines:
        return f"No results found for: {query}"

    return "\n".join(lines)
