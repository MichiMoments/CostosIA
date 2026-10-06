"""Configuración del ETL: variables de entorno, mapeo de grupos de recursos y rutas por defecto."""

import os
from dataclasses import dataclass, field
from pathlib import Path

ETL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ETL_DIR.parent

# Grupo de recursos (en minúsculas) → ambiente del tablero.
# Editar aquí para agregar o mover grupos. "Modelos" sale de MODEL_RGS (abajo).
RG_ENV_MAP = {
    "rg_e_dev_aiuniandes": "Desarrollo",
    "rg_e_dev_aiuniandes_chatmigo": "Desarrollo",
    "rg_e_qa_aiuniandes": "QA",
    "rg_prd_aiuniandes": "Producción",
}

ENVIRONMENTS = ["Desarrollo", "QA", "Producción"]

# Grupos de recursos de modelos de Foundry (Trans_Digital) → costos.json["models"] y general[*]["Modelos"].
# Se consultan a nivel de meter; todo su costo (también alertas, storage...) cuenta como Modelos.
MODEL_RGS = [
    "rg-uniandes-ia-chatmigo-prod",
    "rg-uniandes-ia-chatmigo-qa",
    "rg-uniandes-ia-dsit",
    "rg-uniandes-ia-educacion",
    "rg-uniandes-ia-ingenieria",
    "rg-uniandes-ia-isis",
    "rg-uniandes-ia-plataforma",
    "rg-uniandes-ia-vic",
    "Uniandes-E-PRB-AI_Studio-RG",
]

# Unidad ("tool" en models): primera palabra clave contenida en "<grupo> <recurso>" en minúsculas.
MODEL_TOOL_RULES = [
    ("ingenieria", "Ingenieria"),
    ("isis", "Otras Unidades"),
    ("educacion", "Otras Unidades"),
    ("dsit", "Otras Unidades"),
]
DEFAULT_TOOL = "ChatMigo"

# Primer mes que el ETL escribe en models/Modelos. Los anteriores vienen del cruce manual con el
# CSV de TransDigital (meta.august_source) y no se tocan.
MODELS_FROM = (2026, 9)

# El tablero solo soporta estos años (meta.status2026 / lastData2026 en costos.types.ts).
SUPPORTED_YEAR = 2026


class ConfigError(Exception):
    pass


def load_dotenv(path: Path) -> None:
    """Carga un .env opcional. Las variables ya definidas en el entorno tienen prioridad."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _entero(env, clave: str, defecto: int) -> int:
    valor = env.get(clave)
    if not valor:
        return defecto
    try:
        return int(valor)
    except ValueError:
        raise ConfigError(f"{clave} debe ser un entero, no '{valor}'") from None


@dataclass
class Config:
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_ids: list[str] = field(default_factory=list)
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # llmhub: solo referencias a Key Vault, nunca la key ni el endpoint
    key_vault_uri: str = ""
    llm_secret_api_key: str = ""
    llm_secret_endpoint: str = ""
    llm_model_name: str = "gpt-5.6-terra"
    llm_api_version: str = ""
    llm_max_tokens: int = 4000
    output_dir: Path = REPO_ROOT / "src" / "assets" / "data"
    raw_dir: Path = ETL_DIR / "raw"
    storage_account: str = ""
    storage_container: str = ""
    storage_raw_container: str = "raw"

    @property
    def use_blob(self) -> bool:
        return bool(self.storage_account and self.storage_container)

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(ETL_DIR / ".env")
        env = os.environ

        faltantes = [k for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET") if not env.get(k)]
        if faltantes:
            raise ConfigError(f"Faltan credenciales de Azure: {', '.join(faltantes)}")

        cfg = cls(
            tenant_id=env["AZURE_TENANT_ID"],
            client_id=env["AZURE_CLIENT_ID"],
            client_secret=env["AZURE_CLIENT_SECRET"],
            subscription_ids=[s.strip() for s in env.get("AZURE_SUBSCRIPTION_IDS", "").split(",") if s.strip()],
            llm_provider=(env.get("LLM_PROVIDER") or "gemini").strip().lower(),
            gemini_api_key=env.get("GEMINI_API_KEY", ""),
            gemini_model=env.get("GEMINI_MODEL") or "gemini-3.5-flash",
            key_vault_uri=env.get("AZURE_KEY_VAULT_URI", ""),
            llm_secret_api_key=env.get("LLM_SECRET_API_KEY", ""),
            llm_secret_endpoint=env.get("LLM_SECRET_ENDPOINT", ""),
            llm_model_name=env.get("LLM_MODEL_NAME") or "gpt-5.6-terra",
            llm_api_version=env.get("LLM_API_VERSION", ""),
            llm_max_tokens=_entero(env, "LLM_MAX_TOKENS", 4000),
            storage_account=env.get("AZURE_STORAGE_ACCOUNT", ""),
            storage_container=env.get("AZURE_STORAGE_CONTAINER", ""),
            storage_raw_container=env.get("AZURE_STORAGE_RAW_CONTAINER") or "raw",
        )
        if env.get("OUTPUT_DIR"):
            cfg.output_dir = Path(env["OUTPUT_DIR"])
        if env.get("RAW_DIR"):
            cfg.raw_dir = Path(env["RAW_DIR"])
        return cfg
