"""Lectura de secretos del modelo LLM desde Azure Key Vault (mismo patrón que CA-AIUniandes-RAG-Base).

El .env solo guarda los nombres de los secretos; los valores se resuelven aquí en tiempo de ejecución.
"""

from .config import Config, ConfigError


def _cliente(cfg: Config):
    try:
        from azure.identity import ClientSecretCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as e:
        raise ConfigError(
            "LLM_PROVIDER=llmhub requiere azure-identity y azure-keyvault-secrets "
            "(pip install -r requirements-llmhub.txt)"
        ) from e
    credencial = ClientSecretCredential(cfg.tenant_id, cfg.client_id, cfg.client_secret)
    return SecretClient(vault_url=cfg.key_vault_uri, credential=credencial)


def _leer(cliente, nombre: str, vault: str) -> str:
    try:
        valor = cliente.get_secret(nombre).value
    except Exception as e:
        codigo = getattr(e, "status_code", None)
        if codigo == 404 or type(e).__name__ == "ResourceNotFoundError":
            raise ConfigError(f"El secreto '{nombre}' no existe en {vault}") from e
        if codigo == 403:
            raise ConfigError(
                f"El service principal no tiene permiso para leer '{nombre}' en {vault} "
                "(necesita el rol Key Vault Secrets User)"
            ) from e
        raise ConfigError(f"No se pudo leer el secreto '{nombre}' de {vault}: {e}") from e
    if not valor:
        raise ConfigError(f"El secreto '{nombre}' en {vault} está vacío")
    return valor


def resolver_llm(cfg: Config) -> tuple[str, str]:
    """Devuelve (api_key, endpoint) del modelo leyendo LLM_SECRET_API_KEY y LLM_SECRET_ENDPOINT."""
    cliente = _cliente(cfg)
    return (
        _leer(cliente, cfg.llm_secret_api_key, cfg.key_vault_uri),
        _leer(cliente, cfg.llm_secret_endpoint, cfg.key_vault_uri),
    )
