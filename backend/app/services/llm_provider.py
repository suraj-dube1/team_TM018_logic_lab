"""Provider-independent LLM service with Gemini, OpenAI, and local offline fallback."""

from abc import ABC, abstractmethod
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate response text given a user prompt and optional system instructions."""
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider via REST interface."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.endpoint, json=payload)
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return str(parts[0].get("text", "")).strip()
                return "The authorized documents do not contain enough information to answer this question."
        except Exception as exc:
            logger.exception("Gemini API generation failed; falling back to local synthesizer")
            return LocalSynthesizerProvider().generate(prompt, system_prompt)


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible chat completions provider (Ollama, vLLM, OpenAI, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model_name: str = "gpt-4o-mini",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "VaultRAG",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", "")).strip()
                return "The authorized documents do not contain enough information to answer this question."
        except Exception:
            logger.exception("OpenAI/OpenRouter API call failed; falling back to local synthesizer")
            return LocalSynthesizerProvider().generate(prompt, system_prompt)


class LocalSynthesizerProvider(BaseLLMProvider):
    """Deterministic local extractor for offline execution and automated tests."""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        # Check if prompt contains retrieved sources
        source_pattern = re.compile(r"\[Source (\d+)\](?:\s*\([^)]*\))?:\s*(.*?)(?=\n\[Source|\nQuestion:|$)", re.DOTALL)
        sources = source_pattern.findall(prompt)

        # Extract question
        q_match = re.search(r"Question:\s*(.*?)(?:\nAnswer:|$)", prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else ""

        if not sources:
            return "The authorized documents do not contain enough information to answer this question."

        # Extract salient terms from question
        q_words = {w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", question) if w.lower() not in {"what", "when", "where", "which", "tell", "explain", "does", "have", "with", "from"}}

        relevant_answers: list[str] = []
        for src_num, src_text in sources:
            sentences = [s.strip() for s in re.split(r"[.\n]+", src_text) if len(s.strip()) > 10]
            for sentence in sentences:
                s_words = {w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", sentence)}
                # If there is keyword overlap with the question
                if q_words & s_words:
                    relevant_answers.append(f"{sentence} [Source {src_num}].")
                    break

        if relevant_answers:
            return " ".join(relevant_answers)

        return "The authorized documents do not contain enough information to answer this question."


def get_llm_provider() -> BaseLLMProvider:
    """Instantiate the configured provider or fallback gracefully."""
    settings = get_settings()
    provider_type = (settings.llm_provider or "auto").lower()

    if provider_type in ("openrouter", "auto") and settings.openrouter_api_key:
        logger.info("Using OpenRouter LLM provider (%s)", settings.llm_model_name)
        return OpenAICompatibleProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url or "https://openrouter.ai/api/v1",
            model_name=settings.llm_model_name or "openai/gpt-4o-mini",
        )

    if provider_type in ("gemini", "auto") and settings.gemini_api_key:
        logger.info("Using Gemini LLM provider (%s)", settings.llm_model_name)
        return GeminiProvider(api_key=settings.gemini_api_key, model_name=settings.llm_model_name)

    if provider_type in ("openai", "auto") and settings.openai_api_key:
        logger.info("Using OpenAI-compatible LLM provider")
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            model_name=settings.llm_model_name,
        )

    logger.info("Using local synthesizer LLM provider")
    return LocalSynthesizerProvider()
