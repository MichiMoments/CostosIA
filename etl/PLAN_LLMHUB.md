# Plan: Integrate `llmhub_uniandes` (Azure AI Foundry · gpt-5.6-terra) into costos_etl

## Context
`etl/costos_etl/llm.py` has a stub `KimiLLMHubProvider` that raises `NotImplementedError`. The missing LLMHub library is now available (`UniandesDSIT/Library_Python_Uniandes/llmhub_uniandes`, v0.0.7, commit `96c6945`). It has **no Kimi adapter**. The user chose to use the **Azure OpenAI (Foundry) `gpt-5.6-terra`** deployment through the library. The library will be installed from **Azure Artifacts** using `artifacts-keyring` + Azure CLI (`az login` as the user, who can download it).

### What the library actually is (reviewed from source)
- Builders: `AzureOpenaiConfig().with_api_key().with_model_name().with_endpoint(azure_endpoint).with_azure_deployment().with_api_version()`, plus `with_temperature`, `with_max_tokens`, `with_timeout`, `with_max_retries`, `with_config_additional_param(k, v)`.
- `AzureOpenAIAdapter(config_dict).init_model()` → `langchain.chat_models.init_chat_model(**config)` → a LangChain `BaseChatModel` (`AzureChatOpenAI`). Required keys: `model_provider, model_name, azure_endpoint, azure_deployment, api_version, api_key`.
- `LLMFactory.create_client(builder, AdapterClass)` calls `.build()` itself, so pass the **builder** (the README example is wrong: it imports `llmhub.client.factory` and passes a built dict).
- Deps: `langchain>=0.3.26`, `langchain-openai>=0.3.27`, `langchain-deepseek`.

### Risks to verify first (spike)
1. **`model` kwarg missing.** The config only sets `model_name`. `init_chat_model(model=None, …)` with no `model` returns a *configurable* model that may fail on `.invoke()`. Workaround inside our code: `.with_config_additional_param("model", deployment)`. Confirm that `AzureChatOpenAI` accepts both `model` and `model_name`.
2. **gpt-5.x is a reasoning model.** A custom `temperature` (0.3) is likely rejected, and `max_tokens` → `max_completion_tokens`. Reasoning tokens also eat the budget, so the current 800-token cap could return empty text. Plan: no temperature, `max_completion_tokens` ≈ 4000 (configurable), and optionally `reasoning_effort="low"`.

## Changes

### 1. `etl/costos_etl/llm.py`
- Replace `KimiLLMHubProvider` with `LLMHubAzureOpenAIProvider` (`name = "llmhub"`):
  - Lazy-import `llmhub_uniandes` and `langchain_core.messages` inside `__init__`, the same pattern as the azure-* packages in `storage.py`, so tests and the Gemini path don't need the library. If the import fails → `ConfigError` with an install hint (exit code 2).
  - Build once: `AzureOpenaiConfig()` + key/endpoint/deployment/api_version, `with_model_name(deployment)`, `with_config_additional_param("model", deployment)`, `with_timeout(60)`, `with_max_retries(3)`, `with_config_additional_param("max_completion_tokens", N)`. Then `LLMFactory.create_client(builder, AzureOpenAIAdapter)`.
  - `generate()`: `self.model.invoke([SystemMessage(system_prompt), HumanMessage(user_text)])`, take `.content` (if it's a list of parts, join the text), raise `RuntimeError` if empty, return `strip_markdown(text)`. Reuse the existing `strip_markdown`.
- `get_provider`: `"llmhub"` branch that validates the required settings → `ConfigError`. Remove `"kimi"`, and update the error message to `gemini o llmhub`.
- Gemini stays as it is (default), unchanged.

### 2. `etl/costos_etl/config.py`
- Remove `kimi_api_key`. Add `azure_openai_endpoint`, `azure_openai_api_key`, `azure_openai_deployment` (default `gpt-5.6-terra`), `azure_openai_api_version` (default: the version the Foundry resource shows, to be confirmed), `llm_max_tokens` (default 4000). Read them in `from_env()` with the existing blank → default handling.

### 3. `etl/.env.example`
- `LLM_PROVIDER=gemini  # gemini | llmhub`, and replace `KIMI_API_KEY` with the 4–5 `AZURE_OPENAI_*` variables (empty values).

### 4. Installation (Azure Artifacts)
- New `etl/requirements-llmhub.txt`: `llmhub_uniandes==0.0.7` (+ `langchain-openai`), installed with
  `pip install keyring artifacts-keyring` → `az login` → `pip install -r requirements-llmhub.txt --extra-index-url https://pkgs.dev.azure.com/<org>/<project>/_packaging/<feed>/pypi/simple/`.
  It's kept out of `requirements.txt` so the base install and tests still work without the feed (the lazy import makes it optional). **The feed URL is needed from the user.**
- Note for the future container: inside Docker there is no interactive `az login`, so the build will need `VSS_NIUGET_EXTERNAL_FEED_ENDPOINTS`/PAT or a pipeline `PipAuthenticate@1` task. Documented only, not done (containerization is out of scope).

### 5. Tests — `etl/tests/test_llm.py` (new; no network, no library required)
- `get_provider` with `LLM_PROVIDER=llmhub` and missing vars → `ConfigError`. An unknown provider → `ConfigError`.
- Inject a fake `llmhub_uniandes` + `langchain_core.messages` into `sys.modules` (monkeypatch). Check that the builder receives endpoint/deployment/`model`, that `generate()` sends system + human messages, strips markdown, handles `.content` as a list, and raises on empty text.

### 6. Docs
- `etl/CLAUDE.md`: config section (`LLM_PROVIDER=llmhub`, `AZURE_OPENAI_*`), installation via Artifacts, the `llm.py` row in the table, and remove the "Kimi stub" item from Pending. Mention the two quirks (`model` param, reasoning-model limits).
- Root `CLAUDE.md`: no change needed (the ETL commands are the same).

## Verification
1. Spike (after installing from the feed): a 10-line script that builds the client and calls `.invoke("di hola")` against `gpt-5.6-terra`. It confirms risks 1–2 and the right `api_version`.
2. `python -m pytest etl/tests`: everything passes, including the new `test_llm.py` and the existing `test_tareas_ia_coinciden_con_las_claves_que_usa_la_app`.
3. `cd etl; $env:LLM_PROVIDER="llmhub"; python -m costos_etl --month 2026-09`: 15/15 analyses, `ai-cache.json` regenerated with Spanish text and no markdown. Check that the AI tab shows it in `ng serve` (after a rebuild).
4. `python -m costos_etl --dry-run` with `LLM_PROVIDER=llmhub` and the library not installed still works (no LLM calls, the provider isn't built).

## Open inputs from user
- Azure Artifacts feed URL (org/project/feed).
- Foundry endpoint URL, `api_version`, and confirmation that the deployment name is `gpt-5.6-terra`.
- Whether `llmhub` should become the default `LLM_PROVIDER` (the plan keeps `gemini` as the default).
