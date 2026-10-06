"""Costos de modelos a nivel de meter para costos.json["models"] y general[*]["Modelos"].

Consulta los grupos de config.MODEL_RGS agrupando por meter, asigna la unidad ("tool") por
nombre de recurso y clasifica cada meter en modelo / familia / tipo de token (Entrada, Salida, Otro).
"""

import csv
import io
import re

from . import extract
from .config import DEFAULT_TOOL, MODEL_RGS, MODEL_TOOL_RULES, Config

GROUPING_DETALLE = [
    "ResourceGroupName", "ResourceId", "ServiceName", "MeterCategory", "MeterSubcategory",
    "Meter", "PartNumber", "ServiceFamily",
]
# Si la API no acepta tantas dimensiones: dos consultas unidas por (grupo, meter).
GROUPING_A = ["ResourceGroupName", "ResourceId", "ServiceName", "Meter", "PartNumber"]
GROUPING_B = ["ResourceGroupName", "Meter", "MeterCategory", "MeterSubcategory", "ServiceFamily"]

COLUMNAS_CSV = ["Mes", "SubscriptionName", "Unidad", *GROUPING_DETALLE, "PreTaxCost", "Currency"]

SERVICIOS_MODELO = {"foundry models", "saas"}
METER_MODELO = re.compile(r"tokens?\b|claude", re.IGNORECASE)

TT_SALIDA = re.compile(r"\b(outp|outpt|opt|output)\b")
TT_ENTRADA = re.compile(r"\b(inp|inpt|input|cached|cchd|cd)\b")

# (patrón sobre "<meter> | <subcategoría>" en minúsculas, modelo, familia). Gana el primero que coincide.
REGLAS_MODELO = [
    (r"gpt 5 mini", "GPT-5 Mini", "GPT-5"),
    (r"gpt 5 nano", "GPT-5 Nano", "GPT-5"),
    (r"gpt 5 chat", "GPT-5 Chat", "GPT-5"),
    (r"astra|gpt6", "GPT-6", "GPT-6"),
    (r"luna|^5\.\d+ (nano|mini)", "GPT-5 nano/luna", "GPT-5"),
    (r"chat-latest", "GPT chat-latest", "GPT-5"),
    (r"^gpt 5|^5\.\d", "GPT-5", "GPT-5"),
    (r"gpt 4\.1 mini", "GPT-4.1 Mini", "GPT-4.1"),
    (r"gpt 4\.1 nano", "GPT-4.1 Nano", "GPT-4.1"),
    (r"gpt 4\.1", "GPT-4.1", "GPT-4.1"),
    (r"gpt 4o", "GPT-4o", "GPT-4o"),
    (r"o4-mini", "o4-mini", "o4-mini"),
    (r"gpt-oss", "GPT-OSS", "GPT-OSS"),
    (r"^r1\b", "DeepSeek R1", "DeepSeek"),
    (r"^v4\b", "DeepSeek V4", "DeepSeek"),
    (r"^v3", "DeepSeek V3", "DeepSeek"),
    (r"^k2", "Kimi K2", "Kimi K2"),
]


# Familia de un meter de modelo que ninguna regla reconoce: el merge lo avisa para agregar una regla.
FAM_SIN_CLASIFICAR = "Otros modelos"


def es_modelo(fila: dict) -> bool:
    """Consumo de modelo vs costo adicional (alertas, storage...)."""
    servicio = str(fila.get("ServiceName") or "").strip().lower()
    return servicio in SERVICIOS_MODELO or bool(METER_MODELO.search(str(fila.get("Meter") or "")))


def costo(fila: dict) -> float:
    return float(fila.get("PreTaxCost") or 0.0)


def unidad(fila: dict) -> str:
    """Unidad según palabras clave en el grupo y el nombre del recurso (no en la ruta del proveedor)."""
    recurso = str(fila.get("ResourceId") or "").rstrip("/").split("/")[-1]
    texto = f"{fila.get('ResourceGroupName') or ''} {recurso}".lower()
    for clave, tool in MODEL_TOOL_RULES:
        if clave in texto:
            return tool
    return DEFAULT_TOOL


def meter_key(meter: str) -> str:
    return str(meter or "").strip().lower()


def metadata_existente(costos: dict) -> dict[str, dict]:
    """meter (minúsculas) → fila existente de models, prefiriendo el año más reciente."""
    por_meter = {}
    for year in sorted(costos.get("models", {})):
        for r in costos["models"][year]:
            por_meter[meter_key(r["meter"])] = r
    return por_meter


def _tt(meter: str) -> str:
    m = meter.lower()
    if TT_SALIDA.search(m):
        return "Salida"
    if TT_ENTRADA.search(m):
        return "Entrada"
    return "Otro"


def clasificar(fila: dict, existentes: dict[str, dict]) -> dict:
    """Metadatos de la fila para costos.json: model, fam, tt, family, serviceTier, serviceName, partNumber.

    Reutiliza la clasificación de una fila existente con el mismo meter; si no hay, aplica las reglas.
    """
    meter = str(fila.get("Meter") or "")
    servicio = str(fila.get("ServiceName") or "")
    sub = str(fila.get("MeterSubcategory") or servicio)
    base = {
        "serviceName": servicio,
        "family": sub,
        "serviceTier": sub,
        "partNumber": str(fila.get("PartNumber") or ""),
    }

    previa = existentes.get(meter_key(meter))
    if previa:
        return {**base, **{k: previa[k] for k in ("family", "serviceTier", "model", "fam", "tt")}}

    if not es_modelo(fila):
        if servicio.lower() == "foundry tools":
            return {**base, "model": sub, "fam": "Servicios/Tools", "tt": "Otro"}
        return {**base, "model": servicio or sub, "fam": "Otros", "tt": "Otro"}

    texto = f"{meter} | {sub}".lower()
    if "claude" in texto:
        return {**base, "model": sub if "claude" in sub.lower() else meter, "fam": "Claude", "tt": "Otro"}
    for patron, model, fam in REGLAS_MODELO:
        if re.search(patron, meter.lower()) or re.search(patron, sub.lower()):
            return {**base, "model": model, "fam": fam, "tt": _tt(meter)}
    return {**base, "model": sub or meter, "fam": FAM_SIN_CLASIFICAR, "tt": _tt(meter)}


def unir_pasadas(filas_a: list[dict], filas_b: list[dict]) -> list[dict]:
    """Completa las filas de GROUPING_A con los atributos de meter de GROUPING_B."""
    atributos = {}
    for f in filas_b:
        clave = (str(f.get("ResourceGroupName") or "").lower(), f.get("Meter"))
        atributos[clave] = {k: f.get(k) for k in GROUPING_B if k not in ("ResourceGroupName", "Meter")}
    return [{**atributos.get((str(f.get("ResourceGroupName") or "").lower(), f.get("Meter")), {}), **f} for f in filas_a]


def extraer(cfg: Config, desde: str, hasta: str, rgs: list[str] = MODEL_RGS) -> list[dict]:
    """Filas crudas de la API a nivel de meter para los grupos indicados (con BillingMonth)."""
    # El filtro "In" podría distinguir mayúsculas: se envían ambas variantes.
    filtro = sorted({*rgs, *(rg.lower() for rg in rgs)})
    try:
        filas = extract.extraer_detalle(cfg, desde, hasta, filtro, GROUPING_DETALLE)
        print(f"Modelos: una consulta con {len(GROUPING_DETALLE)} dimensiones")
        return filas
    except extract.BadRequestError as e:
        print(f"La API rechazó la agrupación completa ({e}). Usando dos consultas...")
    filas_a = extract.extraer_detalle(cfg, desde, hasta, filtro, GROUPING_A)
    filas_b = extract.extraer_detalle(cfg, desde, hasta, filtro, GROUPING_B)
    print("Modelos: dos consultas unidas por (grupo, meter)")
    return unir_pasadas(filas_a, filas_b)


def mes_de(fila: dict) -> tuple[int, int]:
    return extract._parse_mes(fila.get("BillingMonth", fila.get("UsageDate")))


def agregar(filas: list[dict], meses: list[tuple[int, int]], costos: dict) -> dict:
    """Devuelve {(año, mes): {(tool, meter_key): {tool, meter, cost, model, fam, tt, ...}}}.

    Cada mes pedido aparece aunque no tenga filas. Los costos se suman sin redondear.
    """
    existentes = metadata_existente(costos)
    resultado: dict = {mes: {} for mes in meses}
    for f in filas:
        mes = mes_de(f)
        if mes not in resultado:
            continue
        meter = str(f.get("Meter") or f.get("ServiceName") or "?").strip()
        tool = unidad(f)
        clave = (tool, meter_key(meter))
        entrada = resultado[mes].get(clave)
        if entrada is None:
            entrada = resultado[mes][clave] = {"tool": tool, "meter": meter, "cost": 0.0, **clasificar(f, existentes)}
        elif not entrada["partNumber"] and f.get("PartNumber"):
            entrada["partNumber"] = str(f["PartNumber"])
        entrada["cost"] += costo(f)
    return resultado


def a_csv(filas: list[dict]) -> str:
    """Archivo crudo por mes: una fila por recurso × meter, con la unidad asignada."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS_CSV, extrasaction="ignore")
    w.writeheader()
    for f in sorted(filas, key=lambda x: (str(x.get("ResourceGroupName")).lower(), -costo(x))):
        y, m = mes_de(f)
        w.writerow({**f, "Mes": f"{y}-{m:02d}", "Unidad": unidad(f)})
    return buf.getvalue()
