"""Proveedores de LLM para el análisis IA. Se elige con LLM_PROVIDER (gemini | llmhub)."""

import re
from typing import Protocol

import requests

from . import keyvault
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


class LLMHubProvider:
    """Azure OpenAI (Foundry) a través de llmhub_uniandes. Recibe la key y el endpoint ya resueltos de Key Vault.

    Igual que CA-AIUniandes-RAG-Base, salvo dos ajustes para modelos de razonamiento (gpt-5.x):
    - "model" explícito: sin él init_chat_model falla ("missing 'model'"), la librería solo pone model_name.
    - sin temperature y con max_completion_tokens (los tokens de razonamiento también cuentan).
    """

    name = "llmhub"

    def __init__(self, api_key: str, endpoint: str, model_name: str, api_version: str, max_tokens: int):
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from llmhub_uniandes.adapters.text.openai import OpenAIAdapter
            from llmhub_uniandes.client.factory import LLMFactory
            from llmhub_uniandes.config.model import AzureOpenaiConfig
        except ImportError as e:
            raise ConfigError(
                "LLM_PROVIDER=llmhub requiere llmhub_uniandes (pip install -r requirements-llmhub.txt "
                "--extra-index-url del feed cedexdevsoftware/pythonPackages)"
            ) from e
        self._mensajes = (SystemMessage, HumanMessage)
        builder = (
            AzureOpenaiConfig()
            .with_api_key(api_key)
            .with_model_name(model_name)
            .with_endpoint(endpoint)
            .with_api_version(api_version)
            .with_azure_deployment(model_name)
            .with_timeout(60)
            .with_max_retries(3)
            .with_config_additional_param("model", model_name)
            .with_config_additional_param("max_completion_tokens", max_tokens)
        )
        self.model = LLMFactory.create_client(config_builder=builder, llm_adapter=OpenAIAdapter)

    def generate(self, system_prompt: str, user_text: str) -> str:
        system, human = self._mensajes
        result = self.model.invoke([system(content=system_prompt), human(content=user_text)])
        content = result.content
        if isinstance(content, list):
            content = "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
        if not content or not content.strip():
            raise RuntimeError("Respuesta vacía de LLMHub (¿max_completion_tokens agotado por el razonamiento?)")
        return strip_markdown(content)


def get_provider(cfg: Config) -> LLMProvider:
    if cfg.llm_provider == "gemini":
        if not cfg.gemini_api_key:
            raise ConfigError("LLM_PROVIDER=gemini requiere GEMINI_API_KEY")
        return GeminiProvider(cfg.gemini_api_key, cfg.gemini_model)
    if cfg.llm_provider == "llmhub":
        requeridas = {
            "AZURE_KEY_VAULT_URI": cfg.key_vault_uri,
            "LLM_SECRET_API_KEY": cfg.llm_secret_api_key,
            "LLM_SECRET_ENDPOINT": cfg.llm_secret_endpoint,
            "LLM_API_VERSION": cfg.llm_api_version,
        }
        faltantes = [k for k, v in requeridas.items() if not v]
        if faltantes:
            raise ConfigError(f"LLM_PROVIDER=llmhub requiere {', '.join(faltantes)}")
        api_key, endpoint = keyvault.resolver_llm(cfg)
        return LLMHubProvider(api_key, endpoint, cfg.llm_model_name, cfg.llm_api_version, cfg.llm_max_tokens)
    raise ConfigError(f"LLM_PROVIDER desconocido: '{cfg.llm_provider}' (usa gemini o llmhub)")
