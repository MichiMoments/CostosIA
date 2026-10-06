# Plan: Integrate `llmhub_uniandes` (Azure AI Foundry · gpt-5.6-terra) into costos_etl

## Context
- `etl/costos_etl/llm.py` has a stub, `KimiLLMHubProvider`, that raises `NotImplementedError`.
- The LLMHub library, `llmhub_uniandes` **0.0.7**, is now **installed** from the Azure Artifacts feed `https://pkgs.dev.azure.com/cedexdevsoftware/_packaging/pythonPackages/pypi/simple/`.
- The library has no Kimi adapter. We'll use the **Azure OpenAI (Foundry) `gpt-5.6-terra`** deployment through it instead.
- **Credentials:** the model's key and endpoint are already stored in **Azure Key Vault**. The ETL must not keep them in `.env`. The ETL only holds the **secret names** for the model it uses, and resolves the values at runtime. This follows the same pattern as RAG-Base, described below.

### Reference implementation: `UniandesDSIT/CA-AIUniandes-RAG-Base` (HEAD `92931c5`)
- **Secrets** (`src/infra/adapters/keyvault_adapter.py`).
  - It reads the vault with `SecretClient(vault_url=AZURE_KEY_VAULT_URI, credential=ClientSecretCredential(tenant, client_id, secret))`.
  - The credential is a service principal, not a managed identity. llmhub never reads Key Vault itself.
- **Model → secret names.**
  - Each model has a Mongo document in `ai_configuration.Model`, defined in `src/domain/models/llm_config.py`.
  - The document holds `{key, api_key: <secret name>, endpoint: <secret name>, model_name, api_version, temperature, additional_params}`.
  - `get_secret()` resolves `api_key` and `endpoint` at runtime.
- **Client** (`src/infra/adapters/llm_adapter.py`):
  ```python
  builder = (AzureOpenaiConfig().with_api_key(api_key).with_model_name(cfg.model_name)
             .with_endpoint(endpoint).with_temperature(cfg.temperature or 0.0)
             .with_api_version(cfg.api_version or "").with_azure_deployment(cfg.model_name))
  for k, v in additional_params.items(): builder = builder.with_config_additional_param(k, v)
  LLMFactory.create_client(config_builder=builder, llm_adapter=OpenAIAdapter)
  ```
  - The deployment equals `model_name`.
  - The adapter is `OpenAIAdapter`. The legacy code in `.info/code/llms.py` used `AzureOpenAIAdapter`.
  - The output is read from `result.content`.
- **Install and CI.**
  - RAG-Base uses `uv`, with `llmhub_uniandes>=0.0.5` (0.0.5 in its lock file) taken from the `cedexdevsoftware/pythonPackages` feed.
  - The Docker build authenticates with a PAT, passed as `UV_INDEX_UNIANDES_PASSWORD`.
  - The pipeline gets the PAT from the variable group `tokens_auth_pipelines`, through the templates in `UniandesDSIT/PipelinesTemplates`.
- **Model types:** RAG-Base only runs gpt-4o and gpt-4o-mini. It has no special handling for reasoning models, which is why the risks below are still open.

### What the library actually is (reviewed from source)
- **Builder methods:**
  - `AzureOpenaiConfig().with_api_key().with_model_name().with_endpoint(azure_endpoint).with_azure_deployment().with_api_version()`
  - also `with_temperature`, `with_max_tokens`, `with_timeout`, `with_max_retries` and `with_config_additional_param(k, v)`.
- **Adapter:** `.init_model()` calls `langchain.chat_models.init_chat_model(**config)` and returns a LangChain `BaseChatModel` (`AzureChatOpenAI`).
- **Factory:** `LLMFactory.create_client(builder, AdapterClass)` calls `.build()` itself, so pass it the **builder**.
- **Dependencies:** `langchain`, `langchain-openai`, `langchain-deepseek`.

### Risks to verify first (spike)
1. **The `model` kwarg is missing.** The config only sets `model_name`. If `model` is absent, `init_chat_model` can return a *configurable* model that fails on `.invoke()`. The fix is `.with_config_additional_param("model", model_name)`.
2. **gpt-5.x is a reasoning model.**
   - A custom `temperature` is likely to be rejected.
   - `max_tokens` has to become `max_completion_tokens`, and reasoning tokens use up part of that budget.
   - Plan: set no temperature, `max_completion_tokens` ≈ 4000 (configurable), and optionally `reasoning_effort="low"`.
3. **`OpenAIAdapter` vs `AzureOpenAIAdapter`.** Start with `OpenAIAdapter`, as RAG-Base does. Fall back to `AzureOpenAIAdapter` if the spike fails.

## Configuration (references only, no secret values)
```
LLM_PROVIDER=llmhub
AZURE_KEY_VAULT_URI=https://<vault>.vault.azure.net/
LLM_SECRET_API_KEY=<name of the secret that holds the key>
LLM_SECRET_ENDPOINT=<name of the secret that holds the endpoint>
LLM_MODEL_NAME=gpt-5.6-terra
LLM_API_VERSION=<api version>
LLM_MAX_TOKENS=4000
```
- The values for the secret names, `model_name` and `api_version` are the `api_key`, `endpoint`, `model_name` and `api_version` fields of the gpt-5.6-terra document in `ai_configuration.Model`.
- To read the vault, the ETL reuses its service principal (`AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET`, the same one used for Cost Management). That principal needs `get` on secrets in the vault: the *Key Vault Secrets User* role or an access policy.

## Changes

### 1. New `etl/costos_etl/keyvault.py`
- `resolver_llm(cfg) -> (api_key, endpoint)`, implemented with `SecretClient` + `ClientSecretCredential(cfg.tenant_id, cfg.client_id, cfg.client_secret)`.
- Name it `keyvault.py`, not `secrets.py`, so it doesn't shadow the stdlib `secrets` module.
- Lazy-import `azure-keyvault-secrets`, following the pattern of the azure-* imports in `storage.py`.
- Map errors to `ConfigError` (exit 2) with a clear message:
  - the secret doesn't exist (`ResourceNotFoundError`)
  - the service principal has no access (403)
  - the package isn't installed
- No Mongo: the ETL reads the secret names from env and doesn't depend on the RAG's database.

### 2. `etl/costos_etl/llm.py`
- **New provider.** Replace `KimiLLMHubProvider` with `LLMHubProvider` (`name = "llmhub"`).
  - It receives the **already resolved** `api_key`/`endpoint`, plus `model_name`, `api_version` and `max_tokens`.
  - Lazy-import `llmhub_uniandes` and `langchain_core.messages`. If the import fails, raise `ConfigError` with an install hint.
- **Client build.** Use the same builder chain as RAG-Base, with these differences:
  - add `with_config_additional_param("model", model_name)` and `("max_completion_tokens", N)`
  - set no temperature
  - add `with_timeout(60)` and `with_max_retries(3)`
  - build the client once, with `LLMFactory.create_client(builder, OpenAIAdapter)`.
- **`generate()`.**
  - Call `invoke([SystemMessage(system_prompt), HumanMessage(user_text)])`.
  - Read `.content`; if it's a list of parts, join their text.
  - Raise `RuntimeError` if the text is empty.
  - Return `strip_markdown(text)`, reusing the existing helper.
- **`get_provider`.**
  - Add an `"llmhub"` branch: validate the references (missing → `ConfigError`), call `keyvault.resolver_llm(cfg)`, then build `LLMHubProvider`.
  - Remove the `"kimi"` branch, and change the error message to `gemini o llmhub`.
- Gemini stays exactly as it is, and remains the default.

### 3. `etl/costos_etl/config.py`
- Remove `kimi_api_key`.
- Add these fields, read in `from_env()` with the existing blank → default handling:
  - `key_vault_uri`
  - `llm_secret_api_key`
  - `llm_secret_endpoint`
  - `llm_model_name` (default `gpt-5.6-terra`)
  - `llm_api_version`
  - `llm_max_tokens` (default 4000)
- Config never stores the key or the endpoint values.

### 4. `etl/.env.example`
- `LLM_PROVIDER=gemini  # gemini | llmhub`.
- Replace `KIMI_API_KEY` with the variables from **Configuration**, left empty.

### 5. Installation
- New file `etl/requirements-llmhub.txt` containing `llmhub_uniandes==0.0.7`, `azure-keyvault-secrets` and `langchain-openai`.
  - A comment at the top says to install `keyring artifacts-keyring` first, then run `pip install -r requirements-llmhub.txt --extra-index-url https://pkgs.dev.azure.com/cedexdevsoftware/_packaging/pythonPackages/pypi/simple/`.
  - Keep it separate from `requirements.txt`, so the base install and the tests keep working without the feed. The lazy imports make the library optional.
- **Future container (documentation only).** Docker has no interactive login, so it needs a PAT with *Packaging (Read)*, passed as a build arg. That's the RAG-Base approach, with the PAT taken from `tokens_auth_pipelines`. The Key Vault access uses the same service principal as the ETL.

### 6. Tests: `etl/tests/test_llm.py` (new; no network and no library required)
- **`keyvault.resolver_llm`.** Use a fake `SecretClient`, injected through `sys.modules`. Check that:
  - it requests the configured secret names
  - a 403 or a missing secret → `ConfigError`.
- **`get_provider`.**
  - `"llmhub"` with missing references → `ConfigError`.
  - An unknown provider → `ConfigError`.
- **Fake `llmhub_uniandes` + `langchain_core.messages`.** Check that:
  - the builder receives the resolved endpoint and key, the deployment, and `model`
  - `generate()` sends the system and human messages
  - markdown is stripped
  - a `.content` list is handled
  - empty text raises an error.

### 7. Docs
- **`etl/CLAUDE.md`:**
  - the config section: `LLM_PROVIDER=llmhub` and the Key Vault references
  - a `keyvault.py` row in the table, and an updated `llm.py` row
  - installation from `cedexdevsoftware/pythonPackages`
  - remove "Kimi stub" from Pending
  - mention the quirks: the `model` param and the reasoning-model limits.
- Root `CLAUDE.md`: no change.

## Verification
1. **Spike.** A short script that:
   - resolves both secrets with `keyvault.resolver_llm`
   - builds the client and calls `.invoke("di hola")` against `gpt-5.6-terra`.
   
   This confirms risks 1–3 and the `api_version`. It must never print the secret values.
2. **Tests.** `python -m pytest etl/tests` passes, including the new `test_llm.py` and the existing `test_tareas_ia_coinciden_con_las_claves_que_usa_la_app`.
3. **Full run.** `cd etl; $env:LLM_PROVIDER="llmhub"; python -m costos_etl --month 2026-09`.
   - All 15 analyses succeed.
   - `ai-cache.json` contains Spanish text with no markdown.
   - The AI tab shows it in `ng serve`, after a rebuild.
4. **Dry run.** `python -m costos_etl --dry-run` with `LLM_PROVIDER=llmhub` still works without Key Vault access. It makes no LLM calls, and neither the provider nor the secrets are resolved.

## Open inputs from user
- The gpt-5.6-terra document from `ai_configuration.Model` (ask your boss). It gives:
  - the vault URI (`AZURE_KEY_VAULT_URI`)
  - the secret name of the key (`api_key`)
  - the secret name of the endpoint (`endpoint`)
  - `model_name`
  - `api_version`
- Confirmation that the ETL service principal (`AZURE_CLIENT_ID`) has `get` on secrets in that vault, or a request to grant it.
- Whether `llmhub` should become the default `LLM_PROVIDER`. The plan keeps `gemini` as the default.
