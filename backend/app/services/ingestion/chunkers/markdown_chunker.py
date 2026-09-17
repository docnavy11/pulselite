import re

import tiktoken

HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
TARGET_TOKENS = 512
MAX_TOKENS = 768


def _count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(text))


MIN_TOKENS = 64


def chunk_markdown(text: str) -> list[dict]:
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    sections = _split_by_headings(text)
    raw_chunks = []

    for section in sections:
        heading_path = section["heading_path"]
        content = section["content"].strip()
        if not content:
            continue

        token_count = _count_tokens(content, encoding)
        if token_count <= MAX_TOKENS:
            raw_chunks.append(
                {
                    "content": content,
                    "heading_path": heading_path,
                    "token_count": token_count,
                }
            )
        else:
            sub_chunks = _split_large_section(content, encoding)
            for sc in sub_chunks:
                raw_chunks.append(
                    {
                        "content": sc["content"],
                        "heading_path": heading_path,
                        "token_count": sc["token_count"],
                    }
                )

    return _merge_small_chunks(raw_chunks, encoding)


def _merge_small_chunks(chunks: list[dict], encoding: tiktoken.Encoding) -> list[dict]:
    """Merge consecutive small chunks until they reach TARGET_TOKENS.

    A chunk is considered small if it's below MIN_TOKENS.  When merging,
    the heading_path of the first chunk in the group is kept.
    """
    if not chunks:
        return []

    merged = []
    buf_parts: list[str] = []
    buf_heading: str | None = None
    buf_tokens = 0

    for chunk in chunks:
        is_small = chunk["token_count"] < MIN_TOKENS

        # If current chunk is large enough on its own, flush buffer first
        if not is_small:
            if buf_parts:
                content = "\n\n".join(buf_parts)
                merged.append(
                    {
                        "content": content,
                        "heading_path": buf_heading,
                        "token_count": _count_tokens(content, encoding),
                    }
                )
                buf_parts = []
                buf_tokens = 0
                buf_heading = None
            merged.append(chunk)
            continue

        # Small chunk — try to accumulate
        if buf_tokens + chunk["token_count"] > TARGET_TOKENS and buf_parts:
            content = "\n\n".join(buf_parts)
            merged.append(
                {
                    "content": content,
                    "heading_path": buf_heading,
                    "token_count": _count_tokens(content, encoding),
                }
            )
            buf_parts = []
            buf_tokens = 0
            buf_heading = None

        if not buf_parts:
            buf_heading = chunk["heading_path"]
        buf_parts.append(chunk["content"])
        buf_tokens += chunk["token_count"]

    if buf_parts:
        content = "\n\n".join(buf_parts)
        merged.append(
            {
                "content": content,
                "heading_path": buf_heading,
                "token_count": _count_tokens(content, encoding),
            }
        )

    return merged


def _split_by_headings(text: str) -> list[dict]:
    lines = text.split("\n")
    sections = []
    current_headings: dict[int, str] = {}
    current_content: list[str] = []

    for line in lines:
        match = HEADING_PATTERN.match(line)
        if match:
            if current_content:
                path = " > ".join(current_headings[k] for k in sorted(current_headings))
                sections.append({"heading_path": path or None, "content": "\n".join(current_content)})
                current_content = []

            level = len(match.group(1))
            heading_text = match.group(2).strip()
            current_headings[level] = heading_text
            keys_to_remove = [k for k in current_headings if k > level]
            for k in keys_to_remove:
                del current_headings[k]
            current_content.append(line)
        else:
            current_content.append(line)

    if current_content:
        path = " > ".join(current_headings[k] for k in sorted(current_headings))
        sections.append({"heading_path": path or None, "content": "\n".join(current_content)})

    return sections


def _split_large_section(text: str, encoding: tiktoken.Encoding) -> list[dict]:
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para, encoding)
        if current_tokens + para_tokens > TARGET_TOKENS and current_chunk:
            content = "\n\n".join(current_chunk)
            chunks.append({"content": content, "token_count": _count_tokens(content, encoding)})
            current_chunk = []
            current_tokens = 0
        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        content = "\n\n".join(current_chunk)
        chunks.append({"content": content, "token_count": _count_tokens(content, encoding)})

    return chunks
