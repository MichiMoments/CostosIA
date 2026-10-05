"""Agrega las filas de costos por mes, ambiente y servicio (antes scripts/filtrar_costos.py + paso manual)."""

import calendar
import csv
import io
from collections import defaultdict
from datetime import date

from .config import ENVIRONMENTS, RG_ENV_MAP, SUPPORTED_YEAR
from .extract import CostRow

MESES_ESPANOL = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class MonthError(Exception):
    pass


def meses_a_procesar(hoy: date, mes: str | None = None) -> list[tuple[int, int]]:
    """Por defecto: el último mes cerrado y el anterior. Con mes='AAAA-MM', solo ese mes."""
    if mes:
        try:
            year, month = (int(p) for p in mes.split("-"))
        except ValueError:
            raise MonthError(f"Mes inválido '{mes}', se espera AAAA-MM")
        if not 1 <= month <= 12:
            raise MonthError(f"Mes inválido '{mes}', se espera AAAA-MM")
        if (year, month) >= (hoy.year, hoy.month):
            raise MonthError(f"{mes} aún no ha cerrado")
        meses = [(year, month)]
    else:
        y, m = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        meses = [(py, pm), (y, m)]

    fuera = [f"{y}-{m:02d}" for y, m in meses if y != SUPPORTED_YEAR]
    if fuera:
        raise MonthError(
            f"El tablero solo soporta {SUPPORTED_YEAR} (meta.status{SUPPORTED_YEAR}); "
            f"no se puede procesar {', '.join(fuera)}. Hay que extender costos.json y costos.types.ts al nuevo año."
        )
    return meses


def rango_iso(meses: list[tuple[int, int]]) -> tuple[str, str]:
    (y0, m0), (y1, m1) = min(meses), max(meses)
    ultimo = calendar.monthrange(y1, m1)[1]
    return f"{y0}-{m0:02d}-01T00:00:00+00:00", f"{y1}-{m1:02d}-{ultimo}T23:59:59+00:00"


def agregar(filas: list[CostRow], meses: list[tuple[int, int]]) -> tuple[dict, set[str]]:
    """Devuelve ({(año, mes): {ambiente: {"total", "services"}}}, grupos_sin_mapear).

    Cada mes trae todos los ambientes, con 0 si no tuvieron costo, para que una
    re-ejecución sobrescriba valores viejos.
    """
    sin_mapear: set[str] = set()
    acumulado = {mes: {env: defaultdict(float) for env in ENVIRONMENTS} for mes in meses}

    for f in filas:
        mes = (f.year, f.month)
        if mes not in acumulado:
            continue
        env = RG_ENV_MAP.get(f.resource_group.strip().lower())
        if env is None:
            sin_mapear.add(f.resource_group)
            continue
        acumulado[mes][env][f.service.strip()] += f.cost

    resultado = {}
    for mes, envs in acumulado.items():
        resultado[mes] = {}
        for env, servicios in envs.items():
            redondeados = {s: round(c, 2) for s, c in sorted(servicios.items(), key=lambda x: -x[1])}
            resultado[mes][env] = {
                "total": round(sum(servicios.values()), 2),
                "services": redondeados,
            }
    return resultado, sin_mapear


def a_csv(filas: list[CostRow]) -> str:
    """Mismo formato de 9 columnas que generaba excelGet.py."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Mes", "Suscripcion", "Grupo_Recursos", "Servicio", "Tipo_Recurso", "Ubicacion", "Recurso_Nombre", "Costo", "Moneda"])
    for f in filas:
        w.writerow([
            f"{MESES_ESPANOL[f.month - 1]} {f.year}", f.subscription, f.resource_group, f.service,
            f.resource_type, f.location, f.resource_name, round(f.cost, 2), f.currency,
        ])
    return buf.getvalue()
