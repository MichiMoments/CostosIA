import sys
import types

import pytest

from costos_etl import keyvault, llm
from costos_etl.config import Config, ConfigError


def cfg_llmhub(**kw):
    base = dict(
        tenant_id="t", client_id="c", client_secret="s", llm_provider="llmhub",
        key_vault_uri="https://kv.vault.azure.net/", llm_secret_api_key="sec-key",
        llm_secret_endpoint="sec-endpoint", llm_api_version="2025-04-01-preview",
    )
    base.update(kw)
    return Config(**base)


def modulos(monkeypatch, **mods):
    """Registra módulos falsos (y sus paquetes padre) en sys.modules."""
    for nombre, attrs in mods.items():
        partes = nombre.split(".")
        for i in range(1, len(partes)):
            monkeypatch.setitem(sys.modules, ".".join(partes[:i]), types.ModuleType(".".join(partes[:i])))
    for nombre, attrs in mods.items():
        mod = types.ModuleType(nombre)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, nombre, mod)


# --- keyvault ---

class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def fake_keyvault(monkeypatch, secretos):
    llamadas = {}

    class Credential:
        def __init__(self, tenant, client, secret):
            llamadas["credential"] = (tenant, client, secret)

    class SecretClient:
        def __init__(self, vault_url, credential):
            llamadas["vault"] = vault_url

        def get_secret(self, nombre):
            valor = secretos[nombre]
            if isinstance(valor, Exception):
                raise valor
            return types.SimpleNamespace(value=valor)

    modulos(
        monkeypatch,
        **{"azure.identity": {"ClientSecretCredential": Credential}, "azure.keyvault.secrets": {"SecretClient": SecretClient}},
    )
    return llamadas


def test_keyvault_resuelve_los_secretos_configurados(monkeypatch):
    llamadas = fake_keyvault(monkeypatch, {"sec-key": "K", "sec-endpoint": "https://e/"})
    assert keyvault.resolver_llm(cfg_llmhub()) == ("K", "https://e/")
    assert llamadas == {"credential": ("t", "c", "s"), "vault": "https://kv.vault.azure.net/"}


@pytest.mark.parametrize("error, texto", [(HttpError(403), "Key Vault Secrets User"), (HttpError(404), "no existe")])
def test_keyvault_errores_son_config_error(monkeypatch, error, texto):
    fake_keyvault(monkeypatch, {"sec-key": error, "sec-endpoint": "x"})
    with pytest.raises(ConfigError, match=texto):
        keyvault.resolver_llm(cfg_llmhub())


def test_keyvault_secreto_vacio(monkeypatch):
    fake_keyvault(monkeypatch, {"sec-key": "K", "sec-endpoint": ""})
    with pytest.raises(ConfigError, match="vacío"):
        keyvault.resolver_llm(cfg_llmhub())


# --- get_provider ---

@pytest.mark.parametrize("campo", ["key_vault_uri", "llm_secret_api_key", "llm_secret_endpoint", "llm_api_version"])
def test_llmhub_sin_referencias(campo):
    with pytest.raises(ConfigError, match="LLM_PROVIDER=llmhub requiere"):
        llm.get_provider(cfg_llmhub(**{campo: ""}))


def test_proveedor_desconocido():
    with pytest.raises(ConfigError, match="gemini o llmhub"):
        llm.get_provider(cfg_llmhub(llm_provider="kimi"))


# --- LLMHubProvider ---

def fake_llmhub(monkeypatch, content):
    estado = {}

    class Builder:
        def __init__(self):
            self.config = {"model_provider": "azure_openai"}

        def __getattr__(self, metodo):
            def setter(*args):
                if metodo == "with_config_additional_param":
                    self.config[args[0]] = args[1]
                else:
                    self.config[metodo.removeprefix("with_")] = args[0]
                return self
            return setter

    class Modelo:
        def invoke(self, mensajes):
            estado["mensajes"] = mensajes
            return types.SimpleNamespace(content=content)

    class Factory:
        @staticmethod
        def create_client(config_builder, llm_adapter):
            estado["config"] = config_builder.config
            estado["adapter"] = llm_adapter
            return Modelo()

    def mensaje(tipo):
        return lambda content: (tipo, content)

    modulos(
        monkeypatch,
        **{
            "langchain_core.messages": {"SystemMessage": mensaje("system"), "HumanMessage": mensaje("human")},
            "llmhub_uniandes.adapters.text.openai": {"OpenAIAdapter": "OpenAIAdapter"},
            "llmhub_uniandes.client.factory": {"LLMFactory": Factory},
            "llmhub_uniandes.config.model": {"AzureOpenaiConfig": Builder},
        },
    )
    return estado


def test_get_provider_llmhub_construye_cliente(monkeypatch):
    fake_keyvault(monkeypatch, {"sec-key": "K", "sec-endpoint": "https://e/"})
    estado = fake_llmhub(monkeypatch, "**Hola** mundo")
    provider = llm.get_provider(cfg_llmhub())

    assert provider.name == "llmhub"
    assert estado["adapter"] == "OpenAIAdapter"
    c = estado["config"]
    assert (c["api_key"], c["endpoint"], c["azure_deployment"], c["model"]) == ("K", "https://e/", "gpt-5.6-terra", "gpt-5.6-terra")
    assert c["api_version"] == "2025-04-01-preview"
    assert c["max_completion_tokens"] == 4000
    assert "temperature" not in c

    assert provider.generate("sistema", "datos") == "Hola mundo"
    assert estado["mensajes"] == [("system", "sistema"), ("human", "datos")]


def test_generate_content_en_partes(monkeypatch):
    fake_llmhub(monkeypatch, [{"type": "text", "text": "uno "}, "dos"])
    provider = llm.LLMHubProvider("K", "https://e/", "m", "v", 100)
    assert provider.generate("s", "u") == "uno dos"


def test_generate_respuesta_vacia(monkeypatch):
    fake_llmhub(monkeypatch, "  ")
    provider = llm.LLMHubProvider("K", "https://e/", "m", "v", 100)
    with pytest.raises(RuntimeError, match="vacía"):
        provider.generate("s", "u")
