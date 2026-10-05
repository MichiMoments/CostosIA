"""Proveedores de LLM para el análisis IA. Se elige con LLM_PROVIDER (gemini | kimi)."""

import re
from typing import Protocol

import requests

from .config import Config, ConfigError


class LLMProvider(Protocol):
    name: str

    def generate(self, system_prompt: str, user_text: str) -> str: ...


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"

    def generate(self, system_prompt: str, user_text: str) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800},
        }
        resp = requests.post(self.url, params={"key": self.api_key}, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            raise RuntimeError("Respuesta vacía de Gemini")
        return strip_markdown(text)


class KimiLLMHubProvider:
    """Kimi a través de la librería LLMHub. Pendiente: implementar cuando la librería esté disponible."""

    name = "kimi"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate(self, system_prompt: str, user_text: str) -> str:
        raise NotImplementedError(
            "El proveedor Kimi (LLMHub) aún no está implementado. Usa LLM_PROVIDER=gemini "
            "o completa KimiLLMHubProvider.generate en etl/costos_etl/llm.py."
        )


def get_provider(cfg: Config) -> LLMProvider:
    if cfg.llm_provider == "gemini":
        if not cfg.gemini_api_key:
            raise ConfigError("LLM_PROVIDER=gemini requiere GEMINI_API_KEY")
        return GeminiProvider(cfg.gemini_api_key, cfg.gemini_model)
    if cfg.llm_provider == "kimi":
        if not cfg.kimi_api_key:
            raise ConfigError("LLM_PROVIDER=kimi requiere KIMI_API_KEY")
        return KimiLLMHubProvider(cfg.kimi_api_key)
    raise ConfigError(f"LLM_PROVIDER desconocido: '{cfg.llm_provider}' (usa gemini o kimi)")
