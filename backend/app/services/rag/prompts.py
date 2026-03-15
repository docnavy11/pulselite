from app.models.knowledge import Chatbot, Chunk

CITATION_INSTRUCTION = """When answering, cite your sources using numbered references like [1], [2], etc.
Only use information from the provided context. If the context doesn't contain enough information to answer the question confidently, say so clearly rather than guessing."""

PERSONA_TEMPLATE = """You are {display_name}, an AI assistant for {chatbot_name}.
Your tone is {tone}. {language_instruction}

{system_prompt}

{citation_instruction}"""


def _build_language_instruction(chatbot: Chatbot) -> str:
    language = chatbot.language or "English"
    if getattr(chatbot, "auto_detect_language", False):
        return (
            "Detect the language of the user's message and always respond in that same language. "
            f"If unsure, default to {language}."
        )
    return f"You respond in {language}."


def build_system_prompt(chatbot: Chatbot) -> str:
    return PERSONA_TEMPLATE.format(
        display_name=chatbot.display_name or "Assistant",
        chatbot_name=chatbot.name,
        tone=chatbot.tone or "professional",
        language_instruction=_build_language_instruction(chatbot),
        system_prompt=chatbot.system_prompt or "",
        citation_instruction=CITATION_INSTRUCTION,
    ).strip()


def build_context_prompt(chunks: list[tuple[Chunk, float]]) -> str:
    if not chunks:
        return "No relevant context found."

    parts = ["Here is the relevant context:\n"]
    for i, (chunk, score) in enumerate(chunks, 1):
        heading = f" ({chunk.heading_path})" if chunk.heading_path else ""
        parts.append(f"[{i}]{heading}:\n{chunk.content}\n")

    return "\n".join(parts)
