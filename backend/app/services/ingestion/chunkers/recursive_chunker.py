import tiktoken

TARGET_TOKENS = 512
OVERLAP_TOKENS = 50
SEPARATORS = ["\n\n", "\n", ". ", " "]


def chunk_recursive(text: str) -> list[dict]:
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    chunks = _recursive_split(text, SEPARATORS, encoding)
    return chunks


def _recursive_split(text: str, separators: list[str], encoding: tiktoken.Encoding) -> list[dict]:
    token_count = len(encoding.encode(text))
    if token_count <= TARGET_TOKENS:
        return [{"content": text.strip(), "heading_path": None, "token_count": token_count}] if text.strip() else []

    separator = separators[0] if separators else " "
    remaining_separators = separators[1:] if len(separators) > 1 else separators

    parts = text.split(separator)
    if len(parts) == 1:
        if remaining_separators and remaining_separators != separators:
            return _recursive_split(text, remaining_separators, encoding)
        return _force_split(text, encoding)

    chunks = []
    current_parts: list[str] = []
    current_tokens = 0

    for part in parts:
        part_tokens = len(encoding.encode(part))
        if current_tokens + part_tokens > TARGET_TOKENS and current_parts:
            content = separator.join(current_parts).strip()
            if content:
                chunks.append({"content": content, "heading_path": None, "token_count": len(encoding.encode(content))})
            current_parts = []
            current_tokens = 0

        if part_tokens > TARGET_TOKENS:
            if current_parts:
                content = separator.join(current_parts).strip()
                if content:
                    chunks.append(
                        {"content": content, "heading_path": None, "token_count": len(encoding.encode(content))}
                    )
                current_parts = []
                current_tokens = 0
            sub_chunks = _recursive_split(part, remaining_separators, encoding)
            chunks.extend(sub_chunks)
        else:
            current_parts.append(part)
            current_tokens += part_tokens

    if current_parts:
        content = separator.join(current_parts).strip()
        if content:
            chunks.append({"content": content, "heading_path": None, "token_count": len(encoding.encode(content))})

    return chunks


def _force_split(text: str, encoding: tiktoken.Encoding) -> list[dict]:
    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), TARGET_TOKENS):
        chunk_tokens = tokens[i : i + TARGET_TOKENS]
        content = encoding.decode(chunk_tokens).strip()
        if content:
            chunks.append({"content": content, "heading_path": None, "token_count": len(chunk_tokens)})
    return chunks
