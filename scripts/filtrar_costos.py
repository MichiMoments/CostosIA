import collections
import csv
import os

GRUPOS_OBJETIVO = {
    "rg_prd_aiuniandes",#
    "rg_e_qa_aiuniandes",#
    "fa-dev-aiuniandes-logs_group",
    "rg_dev_aiuniandes",
    "rg_e_dev_aiuniandes",#
    "rg_e_dev_aiuniandes_chatmigo",#
}

archivo_csv = os.path.join(
    os.path.dirname(__file__),
    "Reporte_Costos_Azure_Todas_Suscripciones_Jul2023_Jul2026 1.csv",
)

filas_filtradas = []

with open(archivo_csv, encoding="utf-8-sig") as f:
    lector = csv.DictReader(f)
    for fila in lector:
        if fila["Grupo_Recursos"].strip() in GRUPOS_OBJETIVO and "agosto" in fila["Mes"].lower():
            filas_filtradas.append(fila)

agrupado = collections.defaultdict(lambda: collections.defaultdict(list))
for fila in filas_filtradas:
    agrupado[fila["Grupo_Recursos"].strip()][fila["Servicio"].strip()].append(fila)

resumen = {}

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

costo_total = sum(r["total"] for r in resumen.values())
ancho_grupo = max(len(g) for g in resumen)
ancho_serv = max(
    len(s) for r in resumen.values() for s in r["servicios"]
)

print("\n" + "=" * 70)
print("  RESUMEN DE COSTOS")
print("=" * 70)
for grupo, datos in resumen.items():
    print(f"\n  {grupo}")
    print(f"  {'-' * (ancho_serv + 20)}")
    for servicio, costo in sorted(datos["servicios"].items(), key=lambda x: -x[1]):
        print(f"    {servicio:<{ancho_serv}}  ${costo:>10,.2f} USD")
    print(f"    {'-' * (ancho_serv + 16)}")
    print(f"    {'SUBTOTAL':<{ancho_serv}}  ${datos['total']:>10,.2f} USD")

print(f"\n  {'=' * (ancho_serv + 20)}")
print(f"    {'TOTAL GENERAL':<{ancho_serv}}  ${costo_total:>10,.2f} USD")
print(f"  {'=' * (ancho_serv + 20)}")
print(f"\n  Total de filas: {len(filas_filtradas)}")
