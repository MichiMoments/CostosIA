"""Fusiona los meses procesados en costos.json (antes scripts/update_costos_json.py).

Solo toca los meses procesados. fusionar() escribe los ambientes y services; fusionar_modelos()
escribe models y general[*]["Modelos"], solo desde config.MODELS_FROM.
"""

import copy
import re

from .config import MODELS_FROM
from .models import FAM_SIN_CLASIFICAR, meter_key

# Ambiente del ETL → clave en costos.json["general"]
ENV_TO_GK = {
    "Desarrollo": "Desarrollo",
    "QA": "Ambiente QA",
    "Producción": "Producción",
}
# Ambiente del ETL → clave en costos.json["services"]
ENV_TO_SK = {
    "Desarrollo": "Desarrollo",
    "QA": "QA",
    "Producción": "Producción",
}

SUFFIXES = [" account", " workspace", " topic", " (v2)", " cache", " service"]


def normalize(name: str) -> str:
    n = name.strip().lower()
    for suf in SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)]
    return re.sub(r"[^a-z0-9]+", "", n)


def fusionar(costos: dict, meses: dict, *, force_zeros: bool = False) -> tuple[dict, list[str]]:
    """Devuelve (costos_actualizado, lineas_de_cambio). No modifica el dict de entrada.

    Si la API devuelve 0 para un ambiente que ya tiene valor en ese mes (p. ej. un mes
    cargado desde otra fuente), se conserva el valor existente salvo con force_zeros.
    """
    costos = copy.deepcopy(costos)
    cambios: list[str] = []
    meta = costos["meta"]

    for (year, month), envs in sorted(meses.items()):
        idx = month - 1
        y = str(year)
        etiqueta = f"{meta['meses'][idx]} {year}"

        for env, datos in envs.items():
            gk, sk = ENV_TO_GK[env], ENV_TO_SK[env]

            serie = costos["general"][y][gk]
            antes = serie[idx]
            if datos["total"] == 0 and antes and not force_zeros:
                cambios.append(f"{etiqueta} · {env}: la API devuelve 0, se conserva {antes:,.2f} USD (usa --force-zeros para sobrescribir)")
                continue
            serie[idx] = datos["total"]
            if antes != datos["total"]:
                cambios.append(f"{etiqueta} · {env}: {antes:,.2f} → {datos['total']:,.2f} USD")

            filas = costos["services"][sk].setdefault(y, [])
            por_nombre = {normalize(r["name"]): r for r in filas}
            vistos = set()
            for servicio, costo in datos["services"].items():
                n = normalize(servicio)
                fila = por_nombre.get(n)
                if fila is None:
                    fila = {"name": servicio, "values": [0.0] * 12, "total": 0.0}
                    filas.append(fila)
                    por_nombre[n] = fila
                    cambios.append(f"{etiqueta} · {env}: servicio nuevo '{servicio}'")
                fila["values"][idx] = costo
                vistos.add(n)

            # Servicios que ya no tienen costo este mes quedan en 0.
            for n, fila in por_nombre.items():
                if n not in vistos:
                    fila["values"][idx] = 0.0
            for fila in filas:
                fila["total"] = round(sum(fila["values"]), 2)

        meta[f"status{y}"][idx] = "full"
        meta[f"lastData{y}"] = max(meta[f"lastData{y}"], idx)

    return costos, cambios


CAMPOS_MODELO = ("serviceName", "family", "serviceTier", "partNumber", "model", "fam", "tt")


def fusionar_modelos(costos: dict, meses: dict, *, force_zeros: bool = False) -> tuple[dict, list[str]]:
    """Fusiona models.agregar() en costos["models"] y general[*]["Modelos"]. No modifica la entrada.

    Las filas se emparejan por (tool, meter en minúsculas); la API no trae PartNumber. Si hay varias
    filas con el mismo meter (distinto part number), la primera recibe el valor y las demás quedan en 0.
    Modelos del mes = suma de los values de models en ese mes.
    """
    costos = copy.deepcopy(costos)
    cambios: list[str] = []
    meses_nombre = costos["meta"]["meses"]

    for (year, month), entradas in sorted(meses.items()):
        idx = month - 1
        y = str(year)
        etiqueta = f"{meses_nombre[idx]} {year}"

        if (year, month) < MODELS_FROM:
            cambios.append(f"{etiqueta} · Modelos: anterior a {MODELS_FROM[0]}-{MODELS_FROM[1]:02d}, se conservan los valores cargados")
            continue

        modelos = costos["general"][y].setdefault("Modelos", [0.0] * 12)
        antes = modelos[idx]
        total_api = round(sum(e["cost"] for e in entradas.values()), 2)
        if total_api == 0 and antes and not force_zeros:
            cambios.append(f"{etiqueta} · Modelos: la API devuelve 0, se conserva {antes:,.2f} USD (usa --force-zeros para sobrescribir)")
            continue

        filas = costos["models"].setdefault(y, [])
        por_clave: dict[tuple[str, str], list[dict]] = {}
        for r in filas:
            por_clave.setdefault((r["tool"], meter_key(r["meter"])), []).append(r)
            r["values"][idx] = 0.0  # lo que no llegue este mes queda en 0

        for clave, e in entradas.items():
            valor = round(e["cost"], 2)
            existentes = por_clave.get(clave)
            if existentes:
                existentes[0]["values"][idx] = valor
                continue
            if valor == 0:
                continue
            fila = {"tool": e["tool"], "meter": e["meter"], **{k: e[k] for k in CAMPOS_MODELO}, "values": [0.0] * 12, "total": 0.0}
            fila["values"][idx] = valor
            filas.append(fila)
            por_clave[clave] = [fila]
            cambios.append(f"{etiqueta} · Modelos: meter nuevo '{e['meter']}' ({e['tool']}, {e['fam']}) {valor:,.2f} USD")
            if e["fam"] == FAM_SIN_CLASIFICAR:
                cambios.append("   (sin regla de familia: agregar un patrón en models.REGLAS_MODELO)")

        for r in filas:
            r["total"] = round(sum(r["values"]), 2)
        modelos[idx] = round(sum(r["values"][idx] for r in filas), 2)
        if antes != modelos[idx]:
            cambios.append(f"{etiqueta} · Modelos: {antes:,.2f} → {modelos[idx]:,.2f} USD")

    return costos, cambios
