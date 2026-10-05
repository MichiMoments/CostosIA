"""Análisis IA precalculado para los 5 gráficos del tablero (antes scripts/generate_ai_cache.py).

Los constructores build_chart1..5 se copiaron sin cambios: definen los prompts y los datos
que recibe el LLM para cada gráfico.
"""

import json
import time
from datetime import datetime, timezone

from .llm import LLMProvider

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


def sum_arr(arr):
    return sum(v or 0 for v in arr)


def sum_range(arr, n):
    return sum_arr(arr[:n])


def annual(general, year, gk):
    return sum_arr(general[year][gk])



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


class AiCacheError(Exception):
    pass


def construir_tareas(data):
    tareas = []
    p, d = build_chart1(data)
    tareas.append(('chart1', p, d))
    p, d = build_chart2(data)
    tareas.append(('chart2', p, d))
    for env in AMB:
        p, d = build_chart3(data, env)
        tareas.append((f'chart3_{env_key(env["label"])}', p, d))
    seg_options = [(-1, 'Total')] + [(i, ENVS[i]['label']) for i in range(len(ENVS))]
    for idx, label in seg_options:
        p, d = build_chart4(data, idx, label)
        tareas.append((f'chart4_{env_key(label)}', p, d))
        p, d = build_chart5(data, idx, label)
        tareas.append((f'chart5_{env_key(label)}', p, d))
    return tareas


def generar(data, provider: LLMProvider, pausa_s: float = 1.5, max_fallos_ratio: float = 0.5) -> dict:
    """Genera las 15 respuestas. Si fallan más de la mitad, lanza AiCacheError."""
    cache = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'provider': provider.name}
    tareas = construir_tareas(data)
    fallos = 0
    print(f'Generando {len(tareas)} análisis IA con {provider.name}...')
    for i, (key, prompt, payload) in enumerate(tareas):
        try:
            cache[key] = provider.generate(prompt, f'Datos del gráfico (JSON):\n{payload}')
            print(f'   [{i + 1}/{len(tareas)}] {key}: ok')
        except Exception as exc:
            fallos += 1
            cache[key] = 'Error al generar el análisis.'
            print(f'   [{i + 1}/{len(tareas)}] {key}: ERROR {exc}')
        if i < len(tareas) - 1:
            time.sleep(pausa_s)
    if fallos > len(tareas) * max_fallos_ratio:
        raise AiCacheError(f'{fallos} de {len(tareas)} análisis fallaron')
    return cache
