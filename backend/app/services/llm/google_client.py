from collections.abc import AsyncGenerator

import google.generativeai as genai

from app.config import settings
from app.services.llm.base import BaseLLMClient


class GoogleLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.GOOGLE_AI_API_KEY

    def _create_model(self, model: str, temperature: float, max_tokens: int, system_instruction: str | None = None):
        client = genai.Client(api_key=self._api_key)
        gen_config = genai.types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )
        return client, model, gen_config

    async def stream_generate(
        self,
        messages: list[dict],
        model: str = "gemini-1.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        history, last_message, system_instruction = self._convert_messages(messages)
        client, model_name, gen_config = self._create_model(model, temperature, max_tokens, system_instruction)

        response = client.models.generate_content(
            model=model_name,
            contents=history + [{"role": "user", "parts": [last_message]}] if last_message else history,
            config=gen_config,
        )
        if response.text:
            yield response.text

    async def generate(
        self,
        messages: list[dict],
        model: str = "gemini-1.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        history, last_message, system_instruction = self._convert_messages(messages)
        client, model_name, gen_config = self._create_model(model, temperature, max_tokens, system_instruction)

        contents = history + [{"role": "user", "parts": [last_message]}] if last_message else history
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=gen_config,
        )
        return response.text

    def _convert_messages(self, messages: list[dict]) -> tuple[list[dict], str, str | None]:
        system_instruction = None
        history = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "assistant":
                history.append({"role": "model", "parts": [msg["content"]]})
            else:
                history.append({"role": "user", "parts": [msg["content"]]})

        last_message = ""
        if history:
            last = history.pop()
            last_message = last["parts"][0]

        return history, last_message, system_instruction
