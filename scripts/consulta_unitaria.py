import requests
import os
import sys
import time
import csv

# ==========================================
# 1. CONFIGURACIÓN Y SEGURIDAD
# ==========================================
def _cargar_env_local():
    """Carga variables desde un archivo .env junto a este script (sin dependencias externas)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith('#') or '=' not in linea:
                    continue
                clave, _, valor = linea.partition('=')
                os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))

_cargar_env_local()

TENANT_ID = os.environ.get('AZURE_TENANT_ID')
CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')

if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
    print("❌ Faltan credenciales de Azure.")
    print("   Define AZURE_TENANT_ID, AZURE_CLIENT_ID y AZURE_CLIENT_SECRET como variables de entorno,")
    print("   o crea un archivo '.env' junto a este script con:")
    print("   AZURE_TENANT_ID=...")
    print("   AZURE_CLIENT_ID=...")
    print("   AZURE_CLIENT_SECRET=...")
    sys.exit(1)

# Suscripción objetivo
SUB_ID = "20e32245-0b90-4bb8-8eaa-c5aee6903f40"
SUB_NOMBRE = "Cedex_Desarrollo_Test"

# Configuración de salida
RUTA_DESCARGA = os.path.dirname(os.path.abspath(__file__))
NOMBRE_ARCHIVO = "costos_transd_ultimo.csv"
RUTA_COMPLETA = os.path.join(RUTA_DESCARGA, NOMBRE_ARCHIVO)

MESES_ESPAÑOL = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

PERIODOS = [
    ("2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00")
]

# ==========================================
# 2. FUNCIONES DE AZURE
# ==========================================
def obtener_token():
    auth_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    auth_data = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': 'https://management.azure.com/.default'
    }
    res = requests.post(auth_url, data=auth_data)
    if res.status_code == 200:
        return res.json().get('access_token')
    else:
        print(f"❌ Error obteniendo token: {res.text}")
        return None

def consultar_costos_periodo(token, sub_id, fecha_inicio, fecha_fin, max_reintentos=8):
    """Consulta los costos para una suscripción y periodo específicos."""
    query_url = f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query?api-version=2023-11-01"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    payload = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": fecha_inicio,
            "to": fecha_fin
        },
        "dataset": {
            "granularity": "Monthly",
            "aggregation": {
                "totalCost": { "name": "PreTaxCost", "function": "Sum" }
            },
            "grouping": [
                { "type": "Dimension", "name": "SubscriptionName" },
                { "type": "Dimension", "name": "ResourceGroupName" },
                { "type": "Dimension", "name": "ServiceName" },
                { "type": "Dimension", "name": "ResourceType" },
                { "type": "Dimension", "name": "ResourceLocation" },
                { "type": "Dimension", "name": "ResourceId" }
            ]
        }
    }

    intento = 0
    while True:
        response = requests.post(query_url, headers=headers, json=payload)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429 and intento < max_reintentos:
            espera = float(response.headers.get('Retry-After', min(2 ** intento, 30)))
            print(f"      ⏳ Límite de tasa alcanzado (429). Reintentando en {espera:.0f}s...")
            time.sleep(espera)
            intento += 1
            continue

        print(f"      ❌ Error {response.status_code} al consultar costos: {response.text[:300]}")
        return None

# ==========================================
# 3. EJECUCIÓN Y GENERACIÓN DE CSV
# ==========================================
token = obtener_token()
todas_las_filas = []

if token:
    print(f"📊 Procesando: {SUB_NOMBRE} ({SUB_ID})")

    for inicio, fin in PERIODOS:
        print(f"   -> Consultando periodo: {inicio[:10]} al {fin[:10]}")
        datos = consultar_costos_periodo(token, SUB_ID, inicio, fin)

        if datos and 'properties' in datos and 'rows' in datos['properties']:
            filas_azure = datos['properties']['rows']
            todas_las_filas.extend(filas_azure)
        else:
            print(f"      ⚠️ Sin datos de costo o error para este periodo.")

    if not todas_las_filas:
        print("\n✅ No se encontraron costos para el periodo definido.")
    else:
        cabeceras = [
            'Mes', 'Suscripcion', 'Grupo_Recursos', 'Servicio',
            'Tipo_Recurso', 'Ubicacion', 'Recurso_Nombre', 'Costo', 'Moneda'
        ]

        filas_procesadas = []
        try:
            with open(RUTA_COMPLETA, mode='w', newline='', encoding='utf-8-sig') as archivo_csv:
                escritor = csv.writer(archivo_csv, delimiter=',')
                escritor.writerow(cabeceras)

                for f in todas_las_filas:
                    costo = round(f[0], 2)

                    fecha_raw = str(f[1])
                    try:
                        fecha_limpia = fecha_raw.split('T')[0].replace("-", "")
                        año_fila = fecha_limpia[:4]
                        mes_num = int(fecha_limpia[4:6])
                        mes_display = f"{MESES_ESPAÑOL[mes_num]} {año_fila}"
                    except (ValueError, KeyError, IndexError):
                        mes_display = fecha_raw

                    suscripcion = f[2]
                    grupo = f[3]
                    servicio = f[4]
                    tipo_recurso = f[5]
                    ubicacion = f[6]

                    id_recurso_completo = str(f[7])
                    nombre_recurso = id_recurso_completo.split('/')[-1] if id_recurso_completo else "N/A"

                    moneda = f[8]

                    fila = [mes_display, suscripcion, grupo, servicio, tipo_recurso, ubicacion, nombre_recurso, costo, moneda]
                    escritor.writerow(fila)
                    filas_procesadas.append(fila)

            print("\n" + "="*60)
            print(f"🚀 PROCESO COMPLETADO CON ÉXITO")
            print(f"📂 Archivo generado en: {RUTA_COMPLETA}")
            print(f"📊 Total de registros: {len(todas_las_filas)}")
            print("="*60)

            # Resumen agrupado por grupo de recursos y servicio
            costo_total = sum(fila[7] for fila in filas_procesadas)
            print(f"\n💰 Costo total {SUB_NOMBRE}: {costo_total:,.2f}")

        except PermissionError:
            print(f"❌ Error: No se pudo escribir el archivo. Asegúrate de que '{NOMBRE_ARCHIVO}' no esté abierto en Excel.")
        except Exception as e:
            print(f"❌ Ocurrió un error inesperado al escribir el archivo: {e}")
else:
    print("❌ Error de autenticación.")
