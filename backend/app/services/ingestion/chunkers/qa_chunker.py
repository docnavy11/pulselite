import re

import tiktoken


def chunk_qa(text: str) -> list[dict]:
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    pairs = _parse_qa_pairs(text)
    chunks = []

    for pair in pairs:
        content = f"Q: {pair['question']}\nA: {pair['answer']}"
        token_count = len(encoding.encode(content))
        chunks.append(
            {
                "content": content,
                "heading_path": None,
                "token_count": token_count,
            }
        )

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
