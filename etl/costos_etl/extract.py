"""Extracción de costos desde la API de Azure Cost Management (antes scripts/excelGet.py)."""

import time
from dataclasses import dataclass

import requests

from .config import Config

ARM = "https://management.azure.com"
COST_API_VERSION = "2023-11-01"

# Mismas dimensiones que excelGet.py para que el CSV crudo siga siendo comparable.
GROUPING = ["SubscriptionName", "ResourceGroupName", "ServiceName", "ResourceType", "ResourceLocation", "ResourceId"]


class ExtractError(Exception):
    pass


class BadRequestError(ExtractError):
    """400 de Cost Management (p. ej. una agrupación que la API no acepta)."""


@dataclass
class CostRow:
    year: int
    month: int
    subscription: str
    resource_group: str
    service: str
    resource_type: str
    location: str
    resource_name: str
    cost: float
    currency: str


def obtener_token(cfg: Config) -> str:
    res = requests.post(
        f"https://login.microsoftonline.com/{cfg.tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "scope": f"{ARM}/.default",
        },
        timeout=30,
    )
    if res.status_code != 200:
        raise ExtractError(f"Error obteniendo token: {res.status_code} {res.text[:300]}")
    return res.json()["access_token"]


def obtener_suscripciones(token: str) -> list[dict]:
    url = f"{ARM}/subscriptions?api-version=2022-12-01"
    headers = {"Authorization": f"Bearer {token}"}
    suscripciones = []
    while url:
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200:
            raise ExtractError(f"Error obteniendo suscripciones: {res.status_code} {res.text[:300]}")
        datos = res.json()
        for sub in datos.get("value", []):
            suscripciones.append({"id": sub["subscriptionId"], "nombre": sub.get("displayName", "Desconocido")})
        url = datos.get("nextLink")
    return suscripciones


def _espera_429(headers, intento: int) -> float:
    """Cost Management indica la espera en x-ms-ratelimit-*-retry-after (segundos), no siempre en Retry-After."""
    valores = [v for k, v in headers.items() if k.lower() == "retry-after" or k.lower().endswith("-retry-after")]
    try:
        espera = max(float(v) for v in valores) if valores else 2 ** intento
    except ValueError:
        espera = 2 ** intento
    return min(max(espera, 1.0), 60.0)


def _post_con_reintentos(url: str, headers: dict, payload: dict, max_reintentos: int = 8) -> dict:
    intento = 0
    while True:
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.RequestException as e:
            if intento >= max_reintentos:
                raise ExtractError(f"Fallo de red al consultar costos tras {intento} reintentos: {e}") from e
            espera = min(2 ** intento, 60)
            print(f"      Fallo de red ({type(e).__name__}). Reintentando en {espera}s...")
            time.sleep(espera)
            intento += 1
            continue

        if res.status_code == 200:
            return res.json()
        if res.status_code == 429 and intento < max_reintentos:
            espera = _espera_429(res.headers, intento)
            print(f"      Límite de tasa (429). Reintentando en {espera:.0f}s...")
            time.sleep(espera)
            intento += 1
            continue
        if res.status_code >= 500 and intento < max_reintentos:
            espera = min(2 ** intento, 60)
            print(f"      Error {res.status_code} de Azure. Reintentando en {espera}s...")
            time.sleep(espera)
            intento += 1
            continue
        error = BadRequestError if res.status_code == 400 else ExtractError
        raise error(f"Error {res.status_code} al consultar costos: {res.text[:300]}")


def consultar_costos(
    token: str, sub_id: str, desde: str, hasta: str, resource_groups: list[str], grouping: list[str] = GROUPING,
) -> list[dict]:
    """Consulta costos mensuales de una suscripción, filtrados por grupo de recursos.

    Devuelve filas como dicts {nombre_columna: valor}, siguiendo nextLink si hay paginación.
    """
    url = f"{ARM}/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query?api-version={COST_API_VERSION}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": desde, "to": hasta},
        "dataset": {
            "granularity": "Monthly",
            "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": d} for d in grouping],
            "filter": {"dimensions": {"name": "ResourceGroupName", "operator": "In", "values": resource_groups}},
        },
    }

    filas = []
    while url:
        datos = _post_con_reintentos(url, headers, payload)
        props = datos.get("properties", {})
        columnas = [c["name"] for c in props.get("columns", [])]
        filas.extend(dict(zip(columnas, r)) for r in props.get("rows", []))
        url = props.get("nextLink")
    return filas


def _parse_mes(valor) -> tuple[int, int]:
    """BillingMonth llega como '2026-09-01T00:00:00' o como entero 20260901."""
    s = str(valor).split("T")[0].replace("-", "")
    return int(s[:4]), int(s[4:6])


def a_cost_row(fila: dict) -> CostRow:
    year, month = _parse_mes(fila.get("BillingMonth", fila.get("UsageDate")))
    resource_id = str(fila.get("ResourceId") or "")
    return CostRow(
        year=year,
        month=month,
        subscription=fila.get("SubscriptionName", ""),
        resource_group=fila.get("ResourceGroupName", ""),
        service=fila.get("ServiceName", ""),
        resource_type=fila.get("ResourceType", ""),
        location=fila.get("ResourceLocation", ""),
        resource_name=resource_id.split("/")[-1] if resource_id else "N/A",
        cost=float(fila.get("PreTaxCost") or 0.0),
        currency=fila.get("Currency", "USD"),
    )


def _suscripciones(cfg: Config, token: str) -> list[dict]:
    if cfg.subscription_ids:
        suscripciones = [{"id": s, "nombre": s} for s in cfg.subscription_ids]
    else:
        suscripciones = obtener_suscripciones(token)
    if not suscripciones:
        raise ExtractError("No se encontraron suscripciones. Verifica el rol 'Cost Management Reader' del service principal.")
    return suscripciones


def extraer(cfg: Config, desde: str, hasta: str, resource_groups: list[str]) -> list[CostRow]:
    token = obtener_token(cfg)
    suscripciones = _suscripciones(cfg, token)

    print(f"Consultando {len(suscripciones)} suscripción(es) de {desde[:10]} a {hasta[:10]}...")
    filas: list[CostRow] = []
    for sub in suscripciones:
        crudas = consultar_costos(token, sub["id"], desde, hasta, resource_groups)
        if crudas:
            print(f"   {sub['nombre']}: {len(crudas)} filas")
        filas.extend(a_cost_row(f) for f in crudas)
        time.sleep(1)  # reduce el throttling de Cost Management entre suscripciones
    return filas


def extraer_detalle(cfg: Config, desde: str, hasta: str, resource_groups: list[str], grouping: list[str]) -> list[dict]:
    """Como extraer(), pero con la agrupación indicada y devolviendo las filas crudas de la API
    (con SubscriptionName añadido si la agrupación no lo trae). Para exploración a nivel de meter."""
    token = obtener_token(cfg)
    suscripciones = _suscripciones(cfg, token)

    print(f"Consultando {len(suscripciones)} suscripción(es) de {desde[:10]} a {hasta[:10]}...")
    filas: list[dict] = []
    for sub in suscripciones:
        crudas = consultar_costos(token, sub["id"], desde, hasta, resource_groups, grouping)
        if crudas:
            print(f"   {sub['nombre']}: {len(crudas)} filas")
        for f in crudas:
            f.setdefault("SubscriptionName", sub["nombre"])
        filas.extend(crudas)
        time.sleep(1)
    return filas
