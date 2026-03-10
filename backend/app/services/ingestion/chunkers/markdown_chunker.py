import re

import tiktoken

HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
TARGET_TOKENS = 512
MAX_TOKENS = 768


def _count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(text))


def chunk_markdown(text: str) -> list[dict]:
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    sections = _split_by_headings(text)
    chunks = []

    for section in sections:
        heading_path = section["heading_path"]
        content = section["content"].strip()
        if not content:
            continue

        token_count = _count_tokens(content, encoding)
        if token_count <= MAX_TOKENS:
            chunks.append(
                {
                    "content": content,
                    "heading_path": heading_path,
                    "token_count": token_count,
                }
            )
        else:
            sub_chunks = _split_large_section(content, encoding)
            for sc in sub_chunks:
                chunks.append(
                    {
                        "content": sc["content"],
                        "heading_path": heading_path,
                        "token_count": sc["token_count"],
                    }
                )

    return chunks


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
