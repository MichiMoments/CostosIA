import collections
import csv
import os

GRUPOS_OBJETIVO = {
    "fa-dev-aiuniandes-logs_group",# 0 - 0   ...Hay otros: fa-dev-aiuniandes-x , x siendo otras cosas | Cedex_Desarrollo_Test
    "rg_prd_aiuniandes",# a - 0 - a | Datacenter DSIT
    "rg_dev_aiuniandes",# 0 - 0 |
    "rg_e_qa_aiuniandes",# a - a | Cedex_Desarrollo_Test
    "rg_e_dev_aiuniandes",# a - a | Cedex_Desarrollo_Test
    "rg_e_dev_aiuniandes_cha  tmigo",# a - a | Cedex_Desarrollo_Test
}

MESES_OBJETIVO = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

archivo_csv = os.path.join(
    os.path.dirname(__file__),
    "Reporte_Costos_Azure_Todas_Suscripciones_2026.csv",
)

filas_por_mes = {mes: [] for mes in MESES_OBJETIVO}

with open(archivo_csv, encoding="utf-8-sig") as f:
    lector = csv.DictReader(f)
    for fila in lector:
        mes_fila = fila["Mes"].lower()
        if fila["Grupo_Recursos"].strip() not in GRUPOS_OBJETIVO:
            continue
        for mes in MESES_OBJETIVO:
            if mes in mes_fila:
                filas_por_mes[mes].append(fila)
                break

resumen_por_mes = {}
total_filas = 0

for mes in MESES_OBJETIVO:
    filas_filtradas = filas_por_mes[mes]
    total_filas += len(filas_filtradas)

    agrupado = collections.defaultdict(lambda: collections.defaultdict(list))
    for fila in filas_filtradas:
        agrupado[fila["Grupo_Recursos"].strip()][fila["Servicio"].strip()].append(fila)

    resumen = {}

    print("\n" + "#" * 70)
    print(f"  MES: {mes.upper()}")
    print("#" * 70)

    for grupo, servicios in agrupado.items():
        subtotal = sum(len(filas) for filas in servicios.values())
        print(f"\n=== {grupo} ===")
        costo_grupo = 0.0
        resumen_servicios = {}
        for servicio, filas in servicios.items():
            costo_servicio = sum(float(fila["Costo"]) for fila in filas)
            costo_grupo += costo_servicio
            resumen_servicios[servicio] = costo_servicio
            print(f"  -- {servicio} ({len(filas)} filas) | Costo: {costo_servicio:.2f} USD --")
            for fila in filas:
                print(f"    {fila['Mes']} | {fila['Recurso_Nombre']} | {fila['Costo']} {fila['Moneda']}")
        print(f"  Subtotal {grupo}: {subtotal} filas | Costo: {costo_grupo:.2f} USD")
        resumen[grupo] = {"servicios": resumen_servicios, "total": costo_grupo}

    resumen_por_mes[mes] = resumen

    if not resumen:
        print(f"\n  (sin datos para {mes})")
        continue

    costo_total_mes = sum(r["total"] for r in resumen.values())
    ancho_serv = max(
        len(s) for r in resumen.values() for s in r["servicios"]
    )

    print("\n" + "=" * 70)
    print(f"  RESUMEN DE COSTOS - {mes.upper()}")
    print("=" * 70)
    for grupo, datos in resumen.items():
        print(f"\n  {grupo}")
        print(f"  {'-' * (ancho_serv + 20)}")
        for servicio, costo in sorted(datos["servicios"].items(), key=lambda x: -x[1]):
            print(f"    {servicio:<{ancho_serv}}  ${costo:>10,.2f} USD")
        print(f"    {'-' * (ancho_serv + 16)}")
        print(f"    {'SUBTOTAL':<{ancho_serv}}  ${datos['total']:>10,.2f} USD")

    print(f"\n  {'=' * (ancho_serv + 20)}")
    print(f"    {'TOTAL ' + mes.upper():<{ancho_serv}}  ${costo_total_mes:>10,.2f} USD")
    print(f"  {'=' * (ancho_serv + 20)}")
    print(f"\n  Total de filas ({mes}): {len(filas_filtradas)}")

costo_total_general = sum(
    r["total"] for resumen in resumen_por_mes.values() for r in resumen.values()
)

print("\n" + "#" * 70)
print("  TOTAL GENERAL (TODOS LOS MESES)")
print("#" * 70)
print(f"    ${costo_total_general:>10,.2f} USD")
print(f"    Total de filas: {total_filas}")
