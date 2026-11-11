"""
Universal Multi-Provider LLM Client supporting:
- Ollama (Local, default)
- Google Gemini (gemini-1.5-flash, gemini-2.0-flash, etc.)
- OpenAI (gpt-4o, gpt-4o-mini, etc.)
- Anthropic Claude (claude-3-5-sonnet, etc.)

No heavy vendor SDK locks: uses direct, robust async HTTP streaming via httpx.
"""

import json
import logging
from typing import AsyncIterator
import httpx

from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM Client providing synchronous string generation and async SSE token streaming.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider = (provider or getattr(settings, "llm_provider", "ollama")).lower()
        self.model = model or getattr(settings, "llm_model", getattr(settings, "ollama_model", "qwen2.5:3b"))
        self.base_url = base_url or getattr(settings, "ollama_base_url", "http://localhost:11434")

        # API Keys from settings or environment
        self.gemini_api_key = getattr(settings, "gemini_api_key", None)
        self.openai_api_key = getattr(settings, "openai_api_key", None)
        self.anthropic_api_key = getattr(settings, "anthropic_api_key", None)

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate full text response from the configured LLM provider."""
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, system_prompt)
        elif self.provider in ("gemini", "google"):
            return await self._generate_gemini(prompt, system_prompt)
        elif self.provider == "openai":
            return await self._generate_openai(prompt, system_prompt)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, system_prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Choose 'ollama', 'gemini', 'openai', or 'anthropic'.")

    async def stream_generate(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        """Stream response tokens from the configured LLM provider."""
        if self.provider == "ollama":
            async for token in self._stream_ollama(prompt, system_prompt):
                yield token
        elif self.provider in ("gemini", "google"):
            async for token in self._stream_gemini(prompt, system_prompt):
                yield token
        elif self.provider == "openai":
            async for token in self._stream_openai(prompt, system_prompt):
                yield token
        elif self.provider == "anthropic":
            async for token in self._stream_anthropic(prompt, system_prompt):
                yield token
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # -------------------------------------------------------------------------
    # Ollama Implementations
    # -------------------------------------------------------------------------
    async def _generate_ollama(self, prompt: str, system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.2,
                "num_predict": getattr(settings, "num_predict", 512),
                "num_ctx": getattr(settings, "num_ctx", 8192),
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    async def _stream_ollama(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            "keep_alive": -1,
            "options": {
                "temperature": 0.2,
                "num_predict": getattr(settings, "num_predict", 512),
                "num_ctx": getattr(settings, "num_ctx", 8192),
            },
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            break
                    except Exception:
                        pass

    # -------------------------------------------------------------------------
    # Google Gemini Implementations
    # -------------------------------------------------------------------------
    async def _generate_gemini(self, prompt: str, system_prompt: str) -> str:
        api_key = self.gemini_api_key or ""
        model_name = self.model if "gemini" in self.model else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json={"contents": contents})
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    async def _stream_gemini(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        api_key = self.gemini_api_key or ""
        model_name = self.model if "gemini" in self.model else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json={"contents": contents}) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        raw_data = line[6:].strip()
                        if not raw_data:
                            continue
                        try:
                            chunk = json.loads(raw_data)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if text:
                                    yield text
                        except Exception:
                            pass

    # -------------------------------------------------------------------------
    # OpenAI Implementations
    # -------------------------------------------------------------------------
    async def _generate_openai(self, prompt: str, system_prompt: str) -> str:
        api_key = self.openai_api_key or ""
        model_name = self.model if self.model not in ("qwen2.5:3b", "llama3.2") else "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {api_key}"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _stream_openai(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        api_key = self.openai_api_key or ""
        model_name = self.model if self.model not in ("qwen2.5:3b", "llama3.2") else "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {api_key}"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", "https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        raw_data = line[6:].strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw_data)
                            token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                yield token
                        except Exception:
                            pass

    # -------------------------------------------------------------------------
    # Anthropic Claude Implementations
    # -------------------------------------------------------------------------
    async def _generate_anthropic(self, prompt: str, system_prompt: str) -> str:
        api_key = self.anthropic_api_key or ""
        model_name = self.model if "claude" in self.model else "claude-3-5-sonnet-20241022"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model_name,
            "max_tokens": getattr(settings, "num_predict", 512),
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"].strip()

    async def _stream_anthropic(self, prompt: str, system_prompt: str) -> AsyncIterator[str]:
        api_key = self.anthropic_api_key or ""
        model_name = self.model if "claude" in self.model else "claude-3-5-sonnet-20241022"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model_name,
            "max_tokens": getattr(settings, "num_predict", 512),
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        raw_data = line[6:].strip()
                        try:
                            chunk = json.loads(raw_data)
                            event_type = chunk.get("type")
                            if event_type == "content_block_delta":
                                token = chunk.get("delta", {}).get("text", "")
                                if token:
                                    yield token
                        except Exception:
                            pass
