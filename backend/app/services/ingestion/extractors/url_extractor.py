import trafilatura


def extract_from_url(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise ValueError(f"Failed to fetch URL: {url}")

    result = trafilatura.extract(downloaded, include_comments=False, include_tables=True, output_format="markdown")
    if result is None:
        raise ValueError(f"Failed to extract content from URL: {url}")

    return result
