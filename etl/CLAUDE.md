# costos_etl — monthly ETL for the cost dashboard

Single Python job that refreshes everything the Angular app reads: `src/assets/data/costos.json` and `ai-cache.json`, plus a raw CSV archive. It replaces the old `scripts/` (excelGet, filtrar_costos, update_costos_json, generate_ai_cache). It is the "Container Apps Job · costos-etl" in `docs/deployment-diagram.html`. It will be containerized and run on a monthly cron, so keep it env-configurable with one entrypoint and meaningful exit codes.

## Commands (run from `etl/`)
- `python -m costos_etl` — last closed month + the one before
- `python -m costos_etl --month 2026-09` — one specific closed month
- `--dry-run` — prints the diff; writes nothing, makes no LLM calls (still calls Azure)
- `--skip-ai` — updates costos.json and leaves ai-cache.json unchanged
- `--force-zeros` — lets a 0 from the API overwrite an existing value
- `python -m costos_etl.explore --month 2026-09 [--include-env-rgs]`: a read-only, meter-level extract of the model RGs (`config.MODEL_RGS`) for debugging. It writes `raw/explore/<YYYY-MM>-models.csv` and prints a summary: per-RG model vs other costs, model × RG, additional costs, and a diff against `models`. It never touches costos.json.
- `python -m pytest etl/tests` (from the repo root) — tests use a copy of the real `costos.json`, with no network

Python 3.11. Dependencies in `requirements.txt` (`requests`; the azure-* packages are only imported when Blob is configured).

## Layout
| Module | Role |
|---|---|
| `__main__.py` | CLI, orchestration, exit codes |
| `config.py` | `Config.from_env()`, optional `.env` loader, **`RG_ENV_MAP`**, `SUPPORTED_YEAR` |
| `extract.py` | Azure token, subscriptions, Cost Management query (RG filter, nextLink paging, retries) → `CostRow` |
| `transform.py` | month resolution, aggregation by month/environment/service, raw CSV formatting |
| `merge.py` | merge into costos.json: `fusionar()` for environments/services (`normalize()`, `ENV_TO_GK`, `ENV_TO_SK`, zero guard) and `fusionar_modelos()` for `models` + `general[*]["Modelos"]` |
| `models.py` | Model costs by meter: `extraer()` (with two-query fallback), `unidad()`, `clasificar()`, `agregar()`, `a_csv()` |
| `ai_cache.py` | `build_chart1..5` (copied verbatim from the old script) + `generar()` |
| `llm.py` | `LLMProvider` protocol: `GeminiProvider`, `KimiLLMHubProvider` (stub) |
| `explore.py` | Read-only model-cost exploration by meter (`resumir()`), reusing `models.py`. Not part of the pipeline |
| `storage.py` | `LocalStorage` (atomic writes) / `BlobStorage` (`DefaultAzureCredential`) |

## Pipeline
1. Resolve the months. The default is (M-1, M), where M is the last closed month. `--month` must already be closed.
2. Extract with one query per subscription for the whole date range, filtered by `ResourceGroupName In RG_ENV_MAP`, monthly granularity.
3. Extract the model RGs (`MODEL_RGS`) at meter level (`models.GROUPING_DETALLE`; falls back to two queries joined by (RG, meter) if the API rejects it).
4. Aggregate. Every environment is present for each month (0 if no rows), and amounts are rounded to 2 decimals. Model rows are summed by (unit, meter).
5. Merge into a deep copy of costos.json: `fusionar()` then `fusionar_modelos()`.
6. Generate the 15 AI analyses (skipped for `--dry-run` or `--skip-ai`).
7. Write, only after every step succeeded: `raw/<YYYY-MM>.csv`, `raw/<YYYY-MM>-models.csv`, `costos.json` (compact), `ai-cache.json` (indent 2). A failure in the models extraction aborts the whole run (exit 3), like any other extraction error.

## Invariants — do not break
- **Incremental only.** Only the processed months are modified. History (2025 and earlier 2026 months) was partly curated by hand (`meta.august_source`) and must stay intact.
- **Models only from `MODELS_FROM` (2026-09).** `models` and `general[*]["Modelos"]` up to Aug 2026 came from the manual TransDigital CSV cross (`meta.august_source`) and are never modified, even when the default run reprocesses August.
- **Modelos = sum of `models[y][*].values[i]`** for every month the ETL writes. All cost in `MODEL_RGS` counts, including alerts, storage, Key Vault and Log Analytics (fam `Otros`, tt `Otro`).
- **Model rows match on `(tool, meter.lower())`.** The API returns an empty `PartNumber`, so existing rows keep their part number. When several rows share a meter (different part numbers), the first gets the month's value and the rest get 0. Rows not seen in a month get 0; new meters whose value rounds to 0 are not added.
- **Classification:** a new meter reuses `model/fam/tt/family/serviceTier` from any existing row with the same meter. Otherwise it uses `models.REGLAS_MODELO`; an unknown model meter gets fam `Otros modelos` and the change log asks for a new rule. The zero guard and `--force-zeros` also apply to Modelos.
- **Zero guard.** If the API returns total 0 for an environment that already has a value in that month, keep the existing value and log it. Real case: August 2026 Producción is $334.96 from "Excel v4", but the Azure RG shows $0. Only `--force-zeros` overrides this.
- **Services not seen in a month** are set to 0 for that month, and each row's `total` is recalculated.
- **Year support is 2026 only** (`SUPPORTED_YEAR`), because the app types use `meta.status2026` / `lastData2026` (`src/app/core/costos.types.ts`). Any month outside 2026 raises `MonthError`. The year rollover requires changing costos.json, the types and this module together.
- **AI cache keys must match what the app reads.** There are 15 keys, `chart1`, `chart2`, `chart3_*` and `chart4/5_*`, and `test_tareas_ia_coinciden_con_las_claves_que_usa_la_app` checks them. Don't change the prompts or keys in `build_chart*` without checking the Angular side.
- **Atomic local writes** (temp file + `os.replace`). A failed run must leave the previous files untouched.

## costos.json shape (what merge touches)
- `meta`: `meses`, `status2026[12]` ("full"/"none"/"partial"), `lastData2026` (0-based index; never decreased).
- `general[year][gk][12]`, where gk is `Desarrollo` | `Ambiente QA` | `Producción` | `Modelos`.
- `services[sk][year]` = list of `{name, values[12], total}`, where sk is `Desarrollo` | `QA` | `Producción`.
- Note that QA uses different keys in the two places: `general` uses "Ambiente QA" and `services` uses "QA" (see `ENV_TO_GK` / `ENV_TO_SK`).
- The API's service names are matched to existing rows through `normalize()`: lowercase, common suffixes stripped (" account", " workspace", " (v2)"…), non-alphanumerics removed. For example, `Storage` matches `Storage account`. Unmatched names are appended as new rows.

## Resource group → environment (`config.RG_ENV_MAP`)
| Resource group | Environment |
|---|---|
| `rg_e_dev_aiuniandes`, `rg_e_dev_aiuniandes_chatmigo` | Desarrollo |
| `rg_e_qa_aiuniandes` | QA |
| `rg_prd_aiuniandes` | Producción |

Matching ignores case. Seen in the data but **not mapped yet**, pending the user's decision:
- `rg-uniandes-e-prb-aiuniandes`, about $500 over Aug–Sep 2026
- the `me_cae-*` Container Apps managed RGs
- `rg-uniandes-ia-chatmigo-prod` and `rg-uniandes-ia-chatmigo-qa` (Trans_Digital)

Because the API filters by this map, unmapped RGs never reach the ETL.

The Foundry model RGs (`rg-uniandes-ia-*` and `Uniandes-E-PRB-AI_Studio-RG`, all in Trans_Digital) are deliberately **not** in `RG_ENV_MAP`. They are in `config.MODEL_RGS` and feed `models` / Modelos.

## Model unit (`tool`) → `config.MODEL_TOOL_RULES`
The first keyword contained in the lowercased `"<RG> <resource name>"` wins (the provider path is ignored): `ingenieria` → Ingenieria; `isis`, `educacion`, `dsit` → Otras Unidades; anything else → `DEFAULT_TOOL` (ChatMigo). AI_Studio-RG holds several units' accounts, which is why the rules use the resource name and not only the RG. The app's Unidad filter (`TOOLS` in `src/app/core/chart.utils.ts`) must contain every unit used.

Cost Management grouping dimensions: `ServiceTier` is rejected, and the name is `MeterSubcategory` (lowercase c). `PartNumber`, `Meter`, `MeterCategory` and `ServiceFamily` are accepted.

## Configuration (env vars; `etl/.env` optional, real env vars win)
- `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` (required). The service principal needs **Cost Management Reader**.
- `AZURE_SUBSCRIPTION_IDS` — optional comma-separated list. Empty means all accessible subscriptions (about 26), which is slower.
- `LLM_PROVIDER` = `gemini` (default) | `kimi`. Then `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-3.5-flash`), `KIMI_API_KEY`.
- `OUTPUT_DIR` (default `<repo>/src/assets/data`), `RAW_DIR` (default `etl/raw`). Raw CSVs must never go in `src/assets`, because they would be bundled.
- `AZURE_STORAGE_ACCOUNT` + `AZURE_STORAGE_CONTAINER`: if both are set, Blob is used instead of local storage. `AZURE_STORAGE_RAW_CONTAINER` defaults to `raw`.
- A blank value in `.env` falls back to the default.
- `.env` and `raw/` are gitignored. Never commit credentials or cost CSVs.

## Exit codes
`0` ok · `2` config/month error · `3` extraction (auth, API, network after retries) · `4` AI cache (more than half of the 15 analyses failed) · `1` unexpected.

## Azure Cost Management quirks
- It throttles heavily (429). The wait time comes in `x-ms-ratelimit-*-retry-after` headers, not always in `Retry-After`; `_espera_429` reads them all, capped at 60 s.
- Up to 8 retries for 429, 5xx and network errors (`ReadTimeout` happens). There is a 1 s pause between subscriptions.
- `BillingMonth` arrives as `"2026-09-01T00:00:00"` or as `20260901`, and `_parse_mes` handles both.
- Rows are read by column name (`properties.columns`), not by position. Large results page through `properties.nextLink`.
- Totals can differ by cents from the old CSV-based numbers. The old CSV rounded each row before summing; the ETL sums exact amounts.

## Pending / known gaps
- `KimiLLMHubProvider.generate` is a stub that raises `NotImplementedError`. Implement it with the LLMHub library once it's available.
- The year rollover for 2027 (see Invariants). A run in February 2027 will exit with code 2.
- The Angular app still imports the JSON at build time (`src/app/core/data.service.ts`), so a rebuild is needed after a run until it fetches from `/data/*` at runtime (see the deployment diagram).
- Containerization (Dockerfile, Container Apps Job, Azure DevOps pipeline) is not done yet.
