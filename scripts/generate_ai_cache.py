"""
generate_ai_cache.py
Generates pre-baked AI analysis for the 5 dashboard charts (15 total responses).
Writes src/assets/data/ai-cache.json — consumed by the Angular app at build time.

Usage:
    cd scripts
    python generate_ai_cache.py
"""

import json, os, re, sys, time
from datetime import datetime, timezone

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COSTOS_JSON = os.path.join(SCRIPT_DIR, '..', 'src', 'assets', 'data', 'costos.json')
OUTPUT_JSON = os.path.join(SCRIPT_DIR, '..', 'src', 'assets', 'data', 'ai-cache.json')

MODEL = 'gemini-3.5-flash'
API_URL = f'https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent'

ENVS = [
    {'gk': 'Desarrollo',   'label': 'Desarrollo'},
    {'gk': 'Ambiente QA',  'label': 'QA'},
    {'gk': 'Producción',   'label': 'Producción'},
    {'gk': 'Modelos',      'label': 'Modelos'},
]

AMB = [
    {'gk': 'Desarrollo',   'label': 'Desarrollo'},
    {'gk': 'Ambiente QA',  'label': 'QA'},
    {'gk': 'Producción',   'label': 'Producción'},
]


def load_env():
    env_path = os.path.join(SCRIPT_DIR, '.env')
    if not os.path.exists(env_path):
        print(f'ERROR: {env_path} not found')
        sys.exit(1)
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()


def load_costos():
    with open(COSTOS_JSON, encoding='utf-8') as f:
        return json.load(f)


def sum_arr(arr):
    return sum(v or 0 for v in arr)


def sum_range(arr, n):
    return sum_arr(arr[:n])


def annual(general, year, gk):
    return sum_arr(general[year][gk])


def strip_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)
    return text.strip()


def call_gemini(api_key, system_prompt, data_json):
    body = {
        'systemInstruction': {
            'parts': [{'text': system_prompt}],
        },
        'contents': [
            {'role': 'user', 'parts': [{'text': f'Datos del gráfico (JSON):\n{data_json}'}]},
        ],
        'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': 800,
        },
    }
    resp = requests.post(f'{API_URL}?key={api_key}', json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    return strip_markdown(text.strip()) if text else 'No se pudo generar el análisis.'


def cmp_series(general, envs, year, idx):
    """idx=-1 for Total, 0..3 for individual ENVS."""
    if idx < 0:
        arr = [0.0] * 12
        for e in envs:
            vals = general[year][e['gk']]
            for i in range(12):
                arr[i] += (vals[i] if i < len(vals) else 0)
        return arr
    return list(general[year][envs[idx]['gk']])


def build_chart1(data):
    meta = data['meta']
    gen = data['general']
    meses = meta['meses']
    n26 = meta['lastData2026'] + 1
    status = meta['status2026']

    env_totals_2025 = [{'ambiente': e['label'], 'total': annual(gen, '2025', e['gk'])} for e in ENVS]
    env_totals_2026 = [{'ambiente': e['label'], 'total': sum_range(gen['2026'][e['gk']], n26)} for e in ENVS]

    t25 = sum(et['total'] for et in env_totals_2025)
    t26 = sum(et['total'] for et in env_totals_2026)

    timeline = []
    for i in range(12):
        timeline.append({'full': f'{meses[i]} 2025', 'partial': False})
    for i in range(n26):
        timeline.append({'full': f'{meses[i]} 2026', 'partial': status[i] == 'partial'})

    series_data = []
    for e in ENVS:
        vals_25 = list(gen['2025'][e['gk']])
        vals_26 = gen['2026'][e['gk']][:n26]
        series_data.append({'name': e['label'], 'data': vals_25 + vals_26})

    detalle = []
    for idx, t in enumerate(timeline):
        vals = []
        for s in series_data:
            vals.append({'ambiente': s['name'], 'usd': s['data'][idx] if idx < len(s['data']) else 0})
        detalle.append({'mes': t['full'], 'parcial': t['partial'], 'valores': vals})

    mes_label = meses[meta['lastData2026']]

    prompt = f"""Eres un analista financiero de costos cloud Azure para el proyecto ChatMigo (plataforma conversacional IA) del área de Transformación Digital. Los valores están en USD. Se muestran 4 ambientes: Desarrollo, QA, Producción y Modelos. Tienes 2025 completo (12 meses) y 2026 hasta el mes más reciente con datos.
Analiza el JSON y responde en 3 puntos breves:
1. Identifica qué ambiente domina el gasto y cuánto representa del total. Menciona cifras concretas en USD.
2. Describe la tendencia mes a mes: si hay picos, caídas abruptas o estacionalidad. Señala los meses específicos donde ocurren cambios relevantes.
3. Compara el comportamiento de 2026 respecto a 2025: si el gasto crece, se reduce o cambia de composición entre ambientes.
Responde en español, texto plano sin formato markdown (sin asteriscos, negritas ni viñetas con *), máximo 120 palabras."""

    payload = json.dumps({
        'proyecto': 'ChatMigo - Transformación Digital',
        'moneda': 'USD',
        'periodoCompleto2025': 'Ene-Dic 2025',
        'periodo2026': f'Ene-{mes_label} 2026',
        'totalGeneral2025': t25,
        'totalGeneral2026': t26,
        'resumenPorAmbiente2025': env_totals_2025,
        'resumenPorAmbiente2026': env_totals_2026,
        'detalleMensual': detalle,
    }, ensure_ascii=False)

    return prompt, payload


def build_chart2(data):
    meta = data['meta']
    gen = data['general']
    meses = meta['meses']
    n26 = meta['lastData2026'] + 1
    mes_label = meses[meta['lastData2026']]

    t25 = sum(annual(gen, '2025', e['gk']) for e in ENVS)
    t26 = sum(annual(gen, '2026', e['gk']) for e in ENVS)

    ambientes = []
    for e in ENVS:
        v25 = annual(gen, '2025', e['gk'])
        v26 = annual(gen, '2026', e['gk'])
        ambientes.append({
            'ambiente': e['label'],
            'total2025_usd': v25,
            'porcentaje2025': round(v25 / t25 * 100, 1) if t25 > 0 else 0,
            'total2026_usd': v26,
            'porcentaje2026': round(v26 / t26 * 100, 1) if t26 > 0 else 0,
            'cambioPct': round((v26 - v25) / v25 * 100, 1) if v25 > 0 else None,
        })

    prompt = f"""Eres un analista financiero de costos cloud Azure para el proyecto ChatMigo (plataforma conversacional IA) del área de Transformación Digital. Los valores están en USD. Se compara el gasto anual TOTAL de 2025 (año completo, 12 meses) contra 2026 (acumulado parcial hasta el mes indicado) por cada ambiente: Desarrollo, QA, Producción y Modelos.
Analiza el JSON y responde en 3 puntos breves:
1. Qué ambiente tuvo el mayor crecimiento o decrecimiento porcentual entre años. Menciona el porcentaje exacto de cambio y las cifras USD.
2. Qué ambiente concentra la mayor proporción del gasto total en cada año y si esa composición cambió.
3. Conclusión ejecutiva: si el gasto general sube o baja y cuál es el principal driver del cambio.
Responde en español, texto plano sin formato markdown (sin asteriscos, negritas ni viñetas con *), máximo 120 palabras."""

    payload = json.dumps({
        'proyecto': 'ChatMigo - Transformación Digital',
        'moneda': 'USD',
        'nota': f'2025 es año completo (12 meses). 2026 es acumulado parcial hasta {mes_label}',
        'totalConsolidado2025': t25,
        'totalConsolidado2026': t26,
        'cambioConsolidadoPct': round((t26 - t25) / t25 * 100, 1) if t25 > 0 else 0,
        'ambientes': ambientes,
    }, ensure_ascii=False)

    return prompt, payload


def build_chart3(data, env):
    meta = data['meta']
    gen = data['general']
    meses = meta['meses']
    n26 = meta['lastData2026'] + 1
    status = meta['status2026']

    vals = gen['2026'][env['gk']][:n26]
    total = sum_arr(vals)
    peak = max(vals)
    peak_idx = vals.index(peak)

    bar_months = []
    for i in range(n26):
        bar_months.append({'full': f'{meses[i]} 2026', 'partial': status[i] == 'partial'})

    prompt = f"""Eres un analista financiero de costos cloud Azure para el proyecto ChatMigo (plataforma conversacional IA) del área de Transformación Digital. Los valores están en USD. Analizas el costo mensual del ambiente "{env['label']}" durante 2026 ({n26} meses con datos).
Analiza el JSON y responde en 3 puntos breves:
1. El mes con mayor gasto (pico), su valor en USD y cuánto representa del total del periodo. Si hay un mes con gasto muy bajo, menciónalo también.
2. La tendencia general: si el gasto viene creciendo, decreciendo o es volátil. Señala si hay algún quiebre o cambio de tendencia entre meses específicos.
3. Variación del último mes con datos respecto al anterior: cuánto subió o bajó en USD y porcentaje.
Responde en español, texto plano sin formato markdown (sin asteriscos, negritas ni viñetas con *), máximo 120 palabras."""

    payload = json.dumps({
        'proyecto': 'ChatMigo - Transformación Digital',
        'moneda': 'USD',
        'ambiente': env['label'],
        'anio': '2026',
        'mesesConDatos': n26,
        'totalPeriodo_usd': round(total, 2),
        'mesPico': bar_months[peak_idx]['full'],
        'valorPico_usd': round(peak, 2),
        'detalleMensual': [{'mes': bar_months[i]['full'], 'usd': vals[i], 'parcial': bar_months[i]['partial']} for i in range(n26)],
    }, ensure_ascii=False)

    return prompt, payload


def build_chart4(data, env_idx, env_label):
    meta = data['meta']
    gen = data['general']
    meses = meta['meses']
    n26 = meta['lastData2026'] + 1
    mes_label = meses[meta['lastData2026']]

    v25 = cmp_series(gen, ENVS, '2025', env_idx)[:n26]
    v26 = cmp_series(gen, ENVS, '2026', env_idx)[:n26]
    total25 = sum_arr(v25)
    total26 = sum_arr(v26)

    prompt = f"""Eres un analista financiero de costos cloud Azure para el proyecto ChatMigo (plataforma conversacional IA) del área de Transformación Digital. Los valores están en USD. Comparas el gasto de "{env_label}" mes a mes entre los primeros {n26} meses de 2025 y los mismos meses de 2026.
Analiza el JSON y responde en 3 puntos breves:
1. Identifica los 2 meses con mayor diferencia absoluta entre 2025 y 2026. Menciona las cifras USD exactas y si fue aumento o reducción.
2. La tendencia general: si 2026 consistentemente gasta más o menos que 2025, o si se invierte en algún punto del año.
3. El acumulado del periodo: cuánto se gastó en total en cada año y cuál es la diferencia porcentual neta.
Responde en español, texto plano sin formato markdown (sin asteriscos, negritas ni viñetas con *), máximo 120 palabras."""

    comparativa = []
    for i in range(n26):
        comparativa.append({
            'mes': meses[i],
            'usd2025': v25[i],
            'usd2026': v26[i],
            'diferencia_usd': round(v26[i] - v25[i], 2),
        })

    payload = json.dumps({
        'proyecto': 'ChatMigo - Transformación Digital',
        'moneda': 'USD',
        'entidad': env_label,
        'periodoComparado': f'Ene-{mes_label} ({n26} meses)',
        'acumulado2025_usd': round(total25, 2),
        'acumulado2026_usd': round(total26, 2),
        'diferenciaPct': round((total26 - total25) / total25 * 100, 1) if total25 > 0 else None,
        'comparativaMensual': comparativa,
    }, ensure_ascii=False)

    return prompt, payload


def build_chart5(data, env_idx, env_label):
    meta = data['meta']
    gen = data['general']
    meses = meta['meses']
    n26 = meta['lastData2026'] + 1
    status = meta['status2026']

    d26 = cmp_series(gen, ENVS, '2026', env_idx)[:n26]

    pts = []
    for i in range(n26):
        pts.append({'full': f'{meses[i]} 2026', 'partial': status[i] == 'partial'})

    last3_pts = pts[-3:]
    last3_vals = d26[-3:]
    total = sum_arr(last3_vals)

    prompt = f"""Eres un analista financiero de costos cloud Azure para el proyecto ChatMigo (plataforma conversacional IA) del área de Transformación Digital. Los valores están en USD. Analizas los últimos 3 meses con datos de 2026 para "{env_label}", mostrando la evolución reciente del gasto.
Analiza el JSON y responde en 3 puntos breves:
1. La tendencia de estos 3 meses: si el gasto sube, baja o fluctúa. Menciona las cifras USD de cada mes.
2. El mes con mayor gasto, su valor exacto y cuánto representa del total de los 3 meses.
3. La variación del último mes respecto al anterior: diferencia en USD y porcentaje. Si la caída o subida es drástica, señálalo.
Responde en español, texto plano sin formato markdown (sin asteriscos, negritas ni viñetas con *), máximo 120 palabras."""

    detalle = []
    for i in range(len(last3_pts)):
        detalle.append({
            'mes': last3_pts[i]['full'],
            'usd': last3_vals[i],
            'porcentajeDelTotal': round(last3_vals[i] / total * 100, 1) if total > 0 else 0,
            'parcial': last3_pts[i]['partial'],
        })

    payload = json.dumps({
        'proyecto': 'ChatMigo - Transformación Digital',
        'moneda': 'USD',
        'entidad': env_label,
        'periodo': 'Últimos 3 meses de 2026 con datos',
        'totalTresMeses_usd': round(total, 2),
        'detalle': detalle,
    }, ensure_ascii=False)

    return prompt, payload


def env_key(label):
    return label.lower().replace('ó', 'o').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ú', 'u')


def main():
    load_env()
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        print('ERROR: GEMINI_API_KEY not set in .env')
        sys.exit(1)

    data = load_costos()
    cache = {'generatedAt': datetime.now(timezone.utc).isoformat()}

    tasks = []

    # Chart 1 (static)
    p, d = build_chart1(data)
    tasks.append(('chart1', p, d))

    # Chart 2 (static)
    p, d = build_chart2(data)
    tasks.append(('chart2', p, d))

    # Chart 3 (per AMB environment, 2026 only)
    for env in AMB:
        key = f'chart3_{env_key(env["label"])}'
        p, d = build_chart3(data, env)
        tasks.append((key, p, d))

    # Charts 4 & 5 (per ENVS + Total)
    seg_options = [(-1, 'Total')] + [(i, ENVS[i]['label']) for i in range(len(ENVS))]
    for idx, label in seg_options:
        key4 = f'chart4_{env_key(label)}'
        p, d = build_chart4(data, idx, label)
        tasks.append((key4, p, d))

        key5 = f'chart5_{env_key(label)}'
        p, d = build_chart5(data, idx, label)
        tasks.append((key5, p, d))

    print(f'Generating {len(tasks)} AI analyses...\n')

    for i, (key, prompt, payload) in enumerate(tasks):
        print(f'[{i+1}/{len(tasks)}] {key}...')
        try:
            text = call_gemini(api_key, prompt, payload)
            cache[key] = text
            print(f'  -> {text[:80]}...\n')
        except Exception as exc:
            print(f'  ERROR: {exc}\n')
            cache[key] = 'Error al generar el análisis.'
        if i < len(tasks) - 1:
            time.sleep(1.5)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f'\nDone. Wrote {len(tasks)} analyses to {OUTPUT_JSON}')


if __name__ == '__main__':
    main()
