"""Exploración de costos de modelos a nivel de meter (el ETL principal ya los carga en costos.json["models"]).

    python -m costos_etl.explore                           # último mes cerrado
    python -m costos_etl.explore --month 2026-09
    python -m costos_etl.explore --month 2026-09 --include-env-rgs

Solo lee: escribe un CSV en <RAW_DIR>/explore/ e imprime un resumen. No toca costos.json ni ai-cache.json.
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date

import requests

from . import extract, storage, transform
from .__main__ import EXIT_CONFIG, EXIT_EXTRACT
from .config import MODEL_RGS, RG_ENV_MAP, Config, ConfigError
from .models import COLUMNAS_CSV, costo as _costo, es_modelo, extraer, unidad


def resumir(filas: list[dict], rgs: list[str]) -> dict:
    """Agrega las filas crudas para el análisis. Los grupos se comparan en minúsculas."""
    por_rg = {rg.lower(): {"modelo": 0.0, "otros": 0.0} for rg in rgs}
    por_modelo: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    otros: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))

    for f in filas:
        rg = str(f.get("ResourceGroupName") or "").lower()
        costo = _costo(f)
        tipo = por_rg.setdefault(rg, {"modelo": 0.0, "otros": 0.0})
        if es_modelo(f):
            tipo["modelo"] += costo
            por_modelo[str(f.get("Meter") or "?")][rg] += costo
        else:
            tipo["otros"] += costo
            otros[rg][(str(f.get("ServiceName") or "?"), str(f.get("Meter") or "?"))] += costo

    con_filas = {str(f.get("ResourceGroupName") or "").lower() for f in filas}
    return {
        "por_rg": por_rg,
        "por_modelo": {m: dict(v) for m, v in por_modelo.items()},
        "otros": {rg: dict(v) for rg, v in otros.items()},
        "sin_filas": [rg for rg in rgs if rg.lower() not in con_filas],
    }


def _imprimir(resumen: dict, costos: dict, year: int, month: int) -> None:
    idx = month - 1

    print("\n== 1. Total por grupo de recursos (USD) ==")
    print(f"   {'grupo':<40}{'modelos':>12}{'otros':>12}{'total':>12}")
    for rg, t in sorted(resumen["por_rg"].items(), key=lambda x: -(x[1]["modelo"] + x[1]["otros"])):
        print(f"   {rg:<40}{t['modelo']:>12,.2f}{t['otros']:>12,.2f}{t['modelo'] + t['otros']:>12,.2f}")

    print("\n== 2. Modelos (meter): total y desglose por grupo ==")
    for meter, por_rg in sorted(resumen["por_modelo"].items(), key=lambda x: -sum(x[1].values())):
        total = sum(por_rg.values())
        if round(total, 2) == 0:
            continue
        detalle = " · ".join(f"{rg} {c:,.2f}" for rg, c in sorted(por_rg.items(), key=lambda x: -x[1]) if round(c, 2))
        print(f"   {meter:<50}{total:>12,.2f}   [{detalle}]")

    print("\n== 3. Costos adicionales (no modelo) por grupo ==")
    for rg, lineas in sorted(resumen["otros"].items()):
        print(f"   {rg}")
        for (servicio, meter), c in sorted(lineas.items(), key=lambda x: -x[1]):
            if round(c, 2):
                print(f"      {servicio:<25}{meter:<45}{c:>10,.2f}")

    print(f"\n== 4. Comparación con costos.json models[{year}] (mes {month}) por meter ==")
    existentes: dict[str, float] = defaultdict(float)
    for r in costos.get("models", {}).get(str(year), []):
        existentes[r["meter"].strip().lower()] += r["values"][idx]
    nuevos: dict[str, float] = defaultdict(float)
    nombres = {}
    for meter, por_rg in resumen["por_modelo"].items():
        nuevos[meter.strip().lower()] += sum(por_rg.values())
        nombres[meter.strip().lower()] = meter
    for clave in sorted(set(existentes) | set(nuevos), key=lambda k: -max(existentes[k], nuevos[k])):
        a, n = existentes[clave], nuevos[clave]
        if round(a, 2) or round(n, 2):
            marca = "=" if abs(a - n) < 0.01 else "≠"
            print(f"   {marca} {nombres.get(clave, clave):<50} json {a:>10,.2f}   api {n:>10,.2f}")

    print("\n== 5. Grupos sin filas ==")
    print("   " + (", ".join(resumen["sin_filas"]) or "ninguno"))


def run(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    year, month = transform.meses_a_procesar(date.today(), args.month)[-1]
    rgs = MODEL_RGS + (sorted(RG_ENV_MAP) if args.include_env_rgs else [])
    costos = storage.get_storage(cfg).read_json("costos.json")

    desde, hasta = transform.rango_iso([(year, month)])
    filas = extraer(cfg, desde, hasta, rgs)
    print(f"Filas extraídas: {len(filas)}")

    destino = cfg.raw_dir / "explore" / f"{year}-{month:02d}-models.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_CSV, extrasaction="ignore")
        w.writeheader()
        for fila in sorted(filas, key=lambda x: (str(x.get("ResourceGroupName")).lower(), -_costo(x))):
            w.writerow({**fila, "Mes": f"{year}-{month:02d}", "Unidad": unidad(fila)})
    print(f"Escrito {destino}")

    _imprimir(resumir(filas, rgs), costos, year, month)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="costos_etl.explore", description="Exploración de costos de modelos por meter")
    parser.add_argument("--month", help="Mes cerrado (AAAA-MM). Por defecto: el último mes cerrado.")
    parser.add_argument("--include-env-rgs", action="store_true", help="Incluye también los grupos de RG_ENV_MAP")
    args = parser.parse_args(argv)

    try:
        return run(args)
    except (ConfigError, transform.MonthError) as e:
        print(f"Error de configuración: {e}", file=sys.stderr)
        return EXIT_CONFIG
    except (extract.ExtractError, requests.RequestException) as e:
        print(f"Error de extracción: {e}", file=sys.stderr)
        return EXIT_EXTRACT


if __name__ == "__main__":
    sys.exit(main())
