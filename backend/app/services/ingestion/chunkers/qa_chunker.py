import re

import tiktoken

TARGET_TOKENS = 512


def chunk_qa(text: str) -> list[dict]:
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    pairs = _parse_qa_pairs(text)

    # Group small Q&A pairs into chunks up to TARGET_TOKENS.
    # Each pair stays atomic — never split across chunks.
    chunks = []
    current_parts: list[str] = []
    current_tokens = 0

    for pair in pairs:
        formatted = f"Q: {pair['question']}\nA: {pair['answer']}"
        pair_tokens = len(encoding.encode(formatted))

        # If adding this pair would exceed target and we already have content, flush
        if current_tokens + pair_tokens > TARGET_TOKENS and current_parts:
            content = "\n\n".join(current_parts)
            chunks.append({
                "content": content,
                "heading_path": None,
                "token_count": len(encoding.encode(content)),
            })
            current_parts = []
            current_tokens = 0

        current_parts.append(formatted)
        current_tokens += pair_tokens

    # Flush remaining
    if current_parts:
        content = "\n\n".join(current_parts)
        chunks.append({
            "content": content,
            "heading_path": None,
            "token_count": len(encoding.encode(content)),
        })

    return chunks


def _parse_qa_pairs(text: str) -> list[dict]:
    patterns = [
        re.compile(r"(?:^|\n)Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:|\Z)", re.DOTALL),
        re.compile(r"(?:^|\n)Question:\s*(.+?)\nAnswer:\s*(.+?)(?=\nQuestion:|\Z)", re.DOTALL),
    ]

    for pattern in patterns:
        matches = pattern.findall(text)
        if matches:
            return [{"question": q.strip(), "answer": a.strip()} for q, a in matches]

    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        pairs.append({"question": lines[i], "answer": lines[i + 1] if i + 1 < len(lines) else ""})

    return pairs
