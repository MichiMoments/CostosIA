import json
from datetime import date
from pathlib import Path

import pytest

from costos_etl import ai_cache, merge, transform
from costos_etl.config import REPO_ROOT
from costos_etl.extract import CostRow, a_cost_row
from costos_etl.storage import LocalStorage

DATA_DIR = REPO_ROOT / "src" / "assets" / "data"


@pytest.fixture
def costos():
    return json.loads((DATA_DIR / "costos.json").read_text(encoding="utf-8"))


def row(rg, service, cost, year=2026, month=9):
    return CostRow(year, month, "Sub", rg, service, "type", "eastus", "res", cost, "USD")


# --- meses_a_procesar ---

def test_meses_por_defecto_ultimo_cerrado_y_anterior():
    assert transform.meses_a_procesar(date(2026, 10, 2)) == [(2026, 8), (2026, 9)]


def test_meses_enero_cruza_al_anio_anterior():
    assert transform.meses_a_procesar(date(2027, 1, 5)) == [(2026, 11), (2026, 12)]


def test_mes_explicito():
    assert transform.meses_a_procesar(date(2026, 10, 2), "2026-07") == [(2026, 7)]


@pytest.mark.parametrize("mes", ["2026-10", "2026-13", "septiembre"])
def test_mes_invalido_o_no_cerrado(mes):
    with pytest.raises(transform.MonthError):
        transform.meses_a_procesar(date(2026, 10, 2), mes)


def test_anio_no_soportado():
    with pytest.raises(transform.MonthError, match="solo soporta 2026"):
        transform.meses_a_procesar(date(2027, 2, 1))


def test_rango_iso_cubre_meses_completos():
    assert transform.rango_iso([(2026, 8), (2026, 9)]) == ("2026-08-01T00:00:00+00:00", "2026-09-30T23:59:59+00:00")


# --- extract ---

@pytest.mark.parametrize("billing_month", ["2026-09-01T00:00:00", 20260901])
def test_a_cost_row_formatos_de_mes(billing_month):
    r = a_cost_row({
        "PreTaxCost": 1.5, "BillingMonth": billing_month, "SubscriptionName": "S",
        "ResourceGroupName": "rg_prd_aiuniandes", "ServiceName": "Functions",
        "ResourceId": "/subscriptions/x/resourceGroups/y/providers/z/fa-prd", "Currency": "USD",
    })
    assert (r.year, r.month, r.resource_name, r.cost) == (2026, 9, "fa-prd", 1.5)


def test_espera_429_usa_cabeceras_de_cost_management():
    from costos_etl.extract import _espera_429
    assert _espera_429({"x-ms-ratelimit-microsoft.costmanagement-entity-retry-after": "20"}, 0) == 20
    assert _espera_429({"Retry-After": "3", "x-ms-ratelimit-microsoft.costmanagement-client-retry-after": "9"}, 0) == 9
    assert _espera_429({}, 3) == 8
    assert _espera_429({"Retry-After": "500"}, 0) == 60


def test_consultar_costos_usa_grouping_por_defecto(monkeypatch):
    from costos_etl import extract
    enviados = []
    monkeypatch.setattr(extract, "_post_con_reintentos", lambda url, h, payload: enviados.append(payload) or {"properties": {}})
    extract.consultar_costos("t", "sub", "a", "b", ["rg"])
    extract.consultar_costos("t", "sub", "a", "b", ["rg"], ["Meter"])
    assert [g["name"] for g in enviados[0]["dataset"]["grouping"]] == extract.GROUPING
    assert [g["name"] for g in enviados[1]["dataset"]["grouping"]] == ["Meter"]


# --- explore ---

def meter_row(rg, service, meter, cost):
    return {"ResourceGroupName": rg, "ServiceName": service, "Meter": meter, "PreTaxCost": cost}


def test_explore_resumir_separa_modelos_y_desglosa_por_grupo():
    from costos_etl import explore
    filas = [
        meter_row("rg-a", "SaaS", "Claude Opus 4.6", 100.0),
        meter_row("RG-B", "SaaS", "Claude Opus 4.6", 50.0),
        meter_row("rg-a", "Foundry Models", "gpt 4.1 Inp glbl Tokens", 10.0),
        meter_row("rg-a", "Azure Monitor", "Alerts Metric Monitored", 2.0),
        meter_row("rg-b", "Azure Monitor", "Alerts Metric Monitored", 1.0),
    ]
    r = explore.resumir(filas, ["rg-a", "RG-B", "rg-c"])
    assert r["por_rg"]["rg-a"] == {"modelo": 110.0, "otros": 2.0}
    assert r["por_rg"]["rg-b"] == {"modelo": 50.0, "otros": 1.0}
    assert r["por_modelo"]["Claude Opus 4.6"] == {"rg-a": 100.0, "rg-b": 50.0}
    assert r["otros"]["rg-a"] == {("Azure Monitor", "Alerts Metric Monitored"): 2.0}
    assert r["sin_filas"] == ["rg-c"]


def test_explore_unir_pasadas():
    from costos_etl import explore
    a = [{"ResourceGroupName": "RG-A", "Meter": "m1", "PreTaxCost": 1.0}]
    b = [{"ResourceGroupName": "rg-a", "Meter": "m1", "MeterSubcategory": "Sub", "ServiceFamily": "F"}]
    assert explore.unir_pasadas(a, b) == [{"ResourceGroupName": "RG-A", "Meter": "m1", "PreTaxCost": 1.0,
                                          "MeterCategory": None, "MeterSubcategory": "Sub",
                                          "ServiceFamily": "F"}]


# --- agregar ---

def test_agregar_mapea_rg_sin_importar_mayusculas_y_reporta_sin_mapear():
    filas = [
        row("RG_PRD_AIUNIANDES", "Functions", 10.004),
        row("rg_prd_aiuniandes", "Functions", 5.0),
        row("rg_e_dev_aiuniandes_chatmigo", "Storage", 1.0),
        row("rg_e_dev_aiuniandes", "Storage", 2.0),
        row("rg_otro", "Storage", 99.0),
        row("rg_prd_aiuniandes", "Functions", 7.0, month=6),  # fuera de los meses pedidos
    ]
    res, sin_mapear = transform.agregar(filas, [(2026, 9)])
    sept = res[(2026, 9)]
    assert sept["Producción"] == {"total": 15.0, "services": {"Functions": 15.0}}
    assert sept["Desarrollo"]["total"] == 3.0
    assert sept["QA"] == {"total": 0.0, "services": {}}
    assert sin_mapear == {"rg_otro"}


# --- fusionar ---

def test_fusionar_actualiza_mes_y_no_toca_modelos(costos):
    modelos_antes = json.dumps(costos["models"]) + json.dumps([costos["general"][y]["Modelos"] for y in costos["general"]])
    original = json.dumps(costos)
    meses = {(2026, 9): {
        "Desarrollo": {"total": 30.0, "services": {"Storage": 10.0, "Servicio Nuevo XYZ": 20.0}},
        "QA": {"total": 0.0, "services": {}},
        "Producción": {"total": 50.0, "services": {"Functions": 50.0}},
    }}

    nuevo, cambios = merge.fusionar(costos, meses)

    assert json.dumps(costos) == original, "no debe mutar la entrada"
    assert nuevo["general"]["2026"]["Desarrollo"][8] == 30.0
    # QA llega en 0 pero ya tenía valor: se conserva
    assert nuevo["general"]["2026"]["Ambiente QA"][8] == costos["general"]["2026"]["Ambiente QA"][8] > 0
    assert any("QA: la API devuelve 0" in c for c in cambios)
    assert nuevo["general"]["2026"]["Producción"][8] == 50.0
    assert nuevo["meta"]["status2026"][8] == "full"
    assert nuevo["meta"]["lastData2026"] == 8

    dev = {r["name"]: r for r in nuevo["services"]["Desarrollo"]["2026"]}
    # "Storage" coincide con la fila existente "Storage account" vía normalize()
    assert dev["Storage account"]["values"][8] == 10.0
    assert "Storage" not in dev
    assert dev["Servicio Nuevo XYZ"]["values"][8] == 20.0
    assert dev["Servicio Nuevo XYZ"]["total"] == 20.0
    # Servicios sin costo este mes quedan en 0 y su total se recalcula
    assert dev["Functions"]["values"][8] == 0.0
    assert dev["Functions"]["total"] == round(sum(dev["Functions"]["values"]), 2)
    # Otros meses intactos
    assert nuevo["general"]["2026"]["Desarrollo"][:8] == costos["general"]["2026"]["Desarrollo"][:8]

    assert json.dumps(nuevo["models"]) + json.dumps([nuevo["general"][y]["Modelos"] for y in nuevo["general"]]) == modelos_antes
    assert any("servicio nuevo 'Servicio Nuevo XYZ'" in c for c in cambios)


def test_fusionar_force_zeros_sobrescribe(costos):
    vacio = {"total": 0.0, "services": {}}
    assert costos["general"]["2026"]["Producción"][7] > 0  # agosto cargado desde Excel v4
    meses = {(2026, 8): {"Desarrollo": vacio, "QA": vacio, "Producción": vacio}}
    conservado, _ = merge.fusionar(costos, meses)
    assert conservado["general"]["2026"]["Producción"][7] == costos["general"]["2026"]["Producción"][7]
    forzado, _ = merge.fusionar(costos, meses, force_zeros=True)
    assert forzado["general"]["2026"]["Producción"][7] == 0.0
    assert all(r["values"][7] == 0.0 for r in forzado["services"]["Producción"]["2026"])


def test_fusionar_no_retrocede_last_data(costos):
    vacio = {"total": 0.0, "services": {}}
    nuevo, _ = merge.fusionar(costos, {(2026, 3): {"Desarrollo": vacio, "QA": vacio, "Producción": vacio}})
    assert nuevo["meta"]["lastData2026"] == costos["meta"]["lastData2026"]


# --- ai_cache ---

class FakeProvider:
    name = "fake"

    def __init__(self, falla=False):
        self.falla = falla
        self.llamadas = 0

    def generate(self, system_prompt, user_text):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("boom")
        return "ok"


def test_tareas_ia_coinciden_con_las_claves_que_usa_la_app(costos):
    claves_app = set(json.loads((DATA_DIR / "ai-cache.json").read_text(encoding="utf-8"))) - {"generatedAt", "provider"}
    assert {k for k, _, _ in ai_cache.construir_tareas(costos)} == claves_app


def test_generar_cache(costos):
    p = FakeProvider()
    cache = ai_cache.generar(costos, p, pausa_s=0)
    assert p.llamadas == 15
    assert cache["chart1"] == "ok" and cache["provider"] == "fake"


def test_generar_cache_falla_si_falla_la_mayoria(costos):
    with pytest.raises(ai_cache.AiCacheError):
        ai_cache.generar(costos, FakeProvider(falla=True), pausa_s=0)


# --- storage ---

def test_local_storage(tmp_path: Path):
    s = LocalStorage(tmp_path / "data", tmp_path / "raw")
    s.write_json("x.json", {"á": 1}, compact=True)
    assert (tmp_path / "data" / "x.json").read_text(encoding="utf-8") == '{"á":1}'
    assert s.read_json("x.json") == {"á": 1}
    s.write_raw("2026-09.csv", "Mes\n")
    assert (tmp_path / "raw" / "2026-09.csv").read_text(encoding="utf-8-sig") == "Mes\n"
    assert [p.name for p in (tmp_path / "data").iterdir()] == ["x.json"]
