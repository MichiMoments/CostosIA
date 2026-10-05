"""ETL mensual del tablero de costos.

    python -m costos_etl                  # último mes cerrado y el anterior
    python -m costos_etl --month 2026-09  # un mes concreto
    python -m costos_etl --dry-run        # muestra los cambios sin escribir ni llamar al LLM
    python -m costos_etl --skip-ai        # actualiza costos.json sin regenerar ai-cache.json
    python -m costos_etl --force-zeros    # deja que un 0 de la API reemplace un valor ya cargado

Códigos de salida: 0 ok · 2 configuración · 3 extracción · 4 análisis IA · 1 otro error.
"""

import argparse
import sys
from datetime import date

import requests

from . import ai_cache, extract, llm, merge, storage, transform
from .config import RG_ENV_MAP, Config, ConfigError

EXIT_CONFIG, EXIT_EXTRACT, EXIT_AI = 2, 3, 4


def run(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    meses = transform.meses_a_procesar(date.today(), args.month)
    provider = None if (args.skip_ai or args.dry_run) else llm.get_provider(cfg)
    store = storage.get_storage(cfg)

    print(f"Meses a procesar: {', '.join(f'{y}-{m:02d}' for y, m in meses)}")
    print(f"Destino: {'Blob ' + cfg.storage_account if cfg.use_blob else cfg.output_dir}")

    costos = store.read_json("costos.json")

    desde, hasta = transform.rango_iso(meses)
    filas = extract.extraer(cfg, desde, hasta, sorted(RG_ENV_MAP))
    print(f"Filas extraídas: {len(filas)}")

    por_mes, sin_mapear = transform.agregar(filas, meses)
    if sin_mapear:
        print(f"Aviso: grupos de recursos sin ambiente asignado (ignorados): {', '.join(sorted(sin_mapear))}")
    for (y, m), envs in sorted(por_mes.items()):
        resumen = " · ".join(f"{env} {d['total']:,.2f}" for env, d in envs.items())
        print(f"   {y}-{m:02d}: {resumen} USD")

    nuevo, cambios = merge.fusionar(costos, por_mes, force_zeros=args.force_zeros)
    print("Cambios en costos.json:" if cambios else "Sin cambios en costos.json.")
    for c in cambios:
        print(f"   {c}")

    if args.dry_run:
        print("Dry run: no se escribió nada.")
        return 0

    cache = ai_cache.generar(nuevo, provider) if provider else None

    # Solo se escribe cuando todo lo anterior salió bien.
    for y, m in meses:
        filas_mes = [f for f in filas if (f.year, f.month) == (y, m)]
        print(f"Escrito {store.write_raw(f'{y}-{m:02d}.csv', transform.a_csv(filas_mes))}")
    print(f"Escrito {store.write_json('costos.json', nuevo, compact=True)}")
    if cache:
        print(f"Escrito {store.write_json('ai-cache.json', cache)}")
    print("ETL completado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="costos_etl", description="ETL mensual del tablero de costos")
    parser.add_argument("--month", help="Mes cerrado a procesar (AAAA-MM). Por defecto: último mes cerrado y el anterior.")
    parser.add_argument("--skip-ai", action="store_true", help="No regenera ai-cache.json")
    parser.add_argument("--dry-run", action="store_true", help="Muestra los cambios sin escribir ni llamar al LLM")
    parser.add_argument("--force-zeros", action="store_true", help="Permite que un 0 de la API reemplace un valor existente")
    args = parser.parse_args(argv)

    try:
        return run(args)
    except (ConfigError, transform.MonthError) as e:
        print(f"Error de configuración: {e}", file=sys.stderr)
        return EXIT_CONFIG
    except (extract.ExtractError, requests.RequestException) as e:
        print(f"Error de extracción: {e}", file=sys.stderr)
        return EXIT_EXTRACT
    except ai_cache.AiCacheError as e:
        print(f"Error en el análisis IA: {e}. No se escribió ningún archivo.", file=sys.stderr)
        return EXIT_AI


if __name__ == "__main__":
    sys.exit(main())
