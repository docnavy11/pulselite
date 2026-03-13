# backend/app/services/autoconfig.py
import json
import logging
import random
import re
from dataclasses import dataclass

from app.services.llm.openrouter_client import OpenRouterLLMClient

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "anthropic/claude-haiku-4-5"

_llm_client = OpenRouterLLMClient()

_DEFAULT_QUESTIONS = [
    "How can I get started?",
    "What are your main features?",
    "How do I contact support?",
    "What pricing plans do you offer?",
]

_TONE_OPTIONS = ["professional", "friendly", "casual", "formal"]

_LANG_NAMES: dict[str, str] = {
    "en": "English", "nl": "Dutch", "fr": "French", "de": "German",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian", "pl": "Polish",
    "ru": "Russian", "tr": "Turkish", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "sv": "Swedish", "da": "Danish",
    "no": "Norwegian", "fi": "Finnish", "cs": "Czech", "ro": "Romanian",
    "hu": "Hungarian", "sk": "Slovak", "bg": "Bulgarian", "hr": "Croatian",
    "uk": "Ukrainian", "el": "Greek", "he": "Hebrew", "th": "Thai",
}

_PROMPT = """You are a chatbot configuration assistant. Based on the website content below, generate a chatbot configuration.

Respond with ONLY a JSON object in this exact format:
{{
  "name": "...",
  "welcome_message": "...",
  "system_prompt": "...",
  "suggested_questions": ["...", "...", "...", "..."],
  "fallback_message": "...",
  "tone": "..."
}}

Rules:
- name: use the actual brand or business name from the content (e.g. "Linkflow Assistant", "QIS Support Bot") — NOT a generic name like "Support Bot"
- welcome_message: friendly greeting in the brand voice, 1-2 sentences
- system_prompt: behavioral guidance ONLY — describe the assistant's persona, tone, scope, and conversation style. Do NOT include specific facts, pricing, product details, or any content from the website. That information is retrieved from the knowledge base at query time.
- suggested_questions: exactly 4 questions visitors commonly ask about this type of business
- fallback_message: polite message for questions outside scope
- tone: infer from the website — must be exactly one of: professional, friendly, casual, formal
{language_instruction}
Website content:
{content}"""

_STRICT_SUFFIX = "\n\nYour response must be ONLY valid JSON, no markdown, no code blocks."


@dataclass
class AutoConfigResult:
    name: str
    welcome_message: str
    system_prompt: str
    suggested_questions: list[str]   # exactly 4 items
    fallback_message: str
    brand_color: str | None          # hex "#RRGGBB" or None
    tone: str                        # professional | friendly | casual | formal


def extract_brand_color(html: str) -> str | None:
    """Extract brand color from HTML. Returns hex string or None."""
    if not html:
        return None

    # Check <meta name="theme-color" content="..."> — both attribute orderings
    meta_patterns = [
        r'<meta\s[^>]*name=["\']theme-color["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta\s[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']theme-color["\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            color = match.group(1).strip()
            if re.match(r'^#[0-9a-fA-F]{3}$', color) or re.match(r'^#[0-9a-fA-F]{6}$', color):
                return color

    # Fallback: scan inline <style> tags for --primary CSS variable
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    for block in style_blocks:
        match = re.search(r'--primary\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})(?=[^0-9a-fA-F]|$)', block, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _parse_llm_response(raw: str) -> dict:
    """Parse JSON from LLM response text. Raises json.JSONDecodeError on failure."""
    text = raw.strip()
    # Strip markdown code fences if present (with optional trailing newline)
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n?```\s*$', '', text)
    return json.loads(text.strip())


async def generate(chunks: list[str], homepage_html: str, language: str | None = None) -> AutoConfigResult:
    """Generate chatbot config from content chunks using Claude Haiku.

    - Sample strategy: first 5 chunks + random sample up to 20 total
    - Single LLM call (Claude Haiku via AnthropicLLMClient)
    - system_prompt capped at 300 words
    - suggested_questions exactly 4 items
    - If LLM returns malformed JSON: retry once with stricter prompt
    - Raise RuntimeError on second failure
    """
    # Sample: first 5 chunks + random sample from remaining, up to 20 total
    first = chunks[:5]
    remaining = chunks[5:]
    extra_needed = max(0, 20 - len(first))
    sampled_extra = random.sample(remaining, min(extra_needed, len(remaining))) if remaining and extra_needed > 0 else []
    sampled_chunks = first + sampled_extra

    content = "\n\n---\n\n".join(sampled_chunks)
    brand_color = extract_brand_color(homepage_html)

    lang_name = _LANG_NAMES.get(language or "", "") if language else ""
    language_instruction = (
        f"- IMPORTANT: Write ALL text fields (welcome_message, system_prompt, suggested_questions, fallback_message) in {lang_name}. Do NOT use English unless the website language is English.\n"
        if lang_name else ""
    )
    prompt_text = _PROMPT.format(content=content, language_instruction=language_instruction)

    raw = await _llm_client.generate(
        messages=[{"role": "user", "content": prompt_text}],
        model=_HAIKU_MODEL,
        temperature=0.3,
        max_tokens=1000,
    )

    try:
        result = _parse_llm_response(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("autoconfig: first LLM response was not valid JSON, retrying with stricter prompt")
        raw_retry = await _llm_client.generate(
            messages=[{"role": "user", "content": prompt_text + _STRICT_SUFFIX}],
            model=_HAIKU_MODEL,
            temperature=0.3,
            max_tokens=1000,
        )
        try:
            result = _parse_llm_response(raw_retry)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError("LLM returned invalid JSON after retry") from exc

    # Cap system_prompt to 300 words
    system_prompt = result.get("system_prompt", "")
    system_prompt = " ".join(system_prompt.split()[:300])

    # Ensure exactly 4 suggested_questions
    questions: list[str] = list(result.get("suggested_questions", []))
    if len(questions) < 4:
        questions = questions + _DEFAULT_QUESTIONS[:4 - len(questions)]
    elif len(questions) > 4:
        questions = questions[:4]

    raw_tone = result.get("tone", "professional")
    tone = raw_tone if raw_tone in _TONE_OPTIONS else "professional"

    return AutoConfigResult(
        name=result.get("name", "Support Bot"),
        welcome_message=result.get("welcome_message", "Hello! How can I help you today?"),
        system_prompt=system_prompt,
        suggested_questions=questions,
        fallback_message=result.get("fallback_message", "I'm sorry, I don't have information on that topic."),
        brand_color=brand_color,
        tone=tone,
    )
