"""Fusiona los meses procesados en costos.json (antes scripts/update_costos_json.py).

Solo toca los meses procesados. "Modelos" (general[*]["Modelos"] y models) no se modifica.
"""

import copy
import re

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
