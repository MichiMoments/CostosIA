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

## 0. Manual setup (done by the user, before implementation)
Windows, PowerShell. The spike (Verification 1) depends on this.

> `az login` here is **your user**, only for the Artifacts feed and for reading the Foundry config. The ETL still authenticates to Cost Management with the service principal (`AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` in `etl/.env`). That doesn't change.

### 0.1 Install the Azure CLI
1. `winget install -e --id Microsoft.AzureCLI`. If winget isn't available, use the MSI from https://aka.ms/installazurecliwindows.
2. Close and reopen the terminal (and VS Code) so PATH updates.
3. Check it works: `az version`.

### 0.2 Sign in with your Uniandes account
1. `az login`. This opens the browser; pick your `@uniandes.edu.co` account.
   - If the browser doesn't open: `az login --use-device-code`.
   - If you land on the wrong tenant: `az login --tenant <tenant-id>`.
2. Check the account: `az account show --query "{user:user.name, tenant:tenantId}"`.

### 0.3 Prepare Python (the ETL's venv)
1. Activate the venv used by `etl/`, or create one: `python -m venv .venv; .\.venv\Scripts\Activate.ps1`.
2. `python -m pip install --upgrade pip` (keyring needs pip ≥ 19.2).
3. `pip install keyring artifacts-keyring`.

### 0.4 Check access to the Azure Artifacts feed
1. Get the feed URL from Azure DevOps: *Artifacts → (feed) → Connect to feed → pip*. It looks like `https://pkgs.dev.azure.com/<org>/<project>/_packaging/<feed>/pypi/simple/`.
2. Test it without installing anything:
   ```powershell
   pip download llmhub_uniandes==0.0.7 --no-deps -d $env:TEMP\llmhub_check --index-url <feed-url>
   ```
   - The first time, artifacts-keyring may open a browser or show a device code. Sign in with the same account.
   - If you get 401/403: check in DevOps that your account has at least *Reader* on the feed (Feed settings → Permissions).
3. **Fallback if keyring doesn't work:** use an az token as the password. `499b84ac-…` is the fixed resource ID for Azure DevOps.
   ```powershell
   $tok = az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv
   pip download llmhub_uniandes==0.0.7 --no-deps -d $env:TEMP\llmhub_check --index-url "https://user:$tok@pkgs.dev.azure.com/<org>/<project>/_packaging/<feed>/pypi/simple/"
   ```
   The token lasts about 1 h. Don't save it in files or scripts.

### 0.5 Get the Foundry credentials (gpt-5.6-terra)
- **Portal:** Azure AI Foundry → project → *Deployments* → `gpt-5.6-terra`. Copy the **endpoint (Target URI)**, the **key** and the **api-version** (it's in the URI query string).
- **Or by CLI** (needs Reader on the resource; listing keys needs Contributor or *Cognitive Services User*):
  ```powershell
  az account set --subscription "<Trans_Digital subscription>"
  az cognitiveservices account show -n <resource> -g <rg> --query properties.endpoint -o tsv
  az cognitiveservices account deployment list -n <resource> -g <rg> --query "[].{name:name, model:properties.model.name, version:properties.model.version}" -o table
  az cognitiveservices account keys list -n <resource> -g <rg> --query key1 -o tsv
  ```
- Put them in `etl/.env` (gitignored, never commit):
  ```
  AZURE_OPENAI_ENDPOINT=
  AZURE_OPENAI_API_KEY=
  AZURE_OPENAI_DEPLOYMENT=gpt-5.6-terra
  AZURE_OPENAI_API_VERSION=
  ```

### 0.6 Done when
- [ ] `az account show` shows your account.
- [ ] The `pip download` from 0.4 succeeds.
- [ ] `etl/.env` has the 4 `AZURE_OPENAI_*` values.

Then implementation starts: §4 installs the library for real, then the spike.

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
- New `etl/requirements-llmhub.txt`: `llmhub_uniandes==0.0.7` (+ `langchain-openai`). After the manual setup (§0), install it with
  `pip install -r requirements-llmhub.txt --extra-index-url <feed-url>`.
  It's kept out of `requirements.txt` so the base install and tests still work without the feed (the lazy import makes it optional). **The feed URL is needed from the user.**
- Note for the future container: inside Docker there is no interactive `az login`, so the build will need `VSS_NUGET_EXTERNAL_FEED_ENDPOINTS`/PAT or a pipeline `PipAuthenticate@1` task. Documented only, not done (containerization is out of scope).

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
- Foundry resource name, its RG and subscription (for the `az` commands in §0.5).
- Whether `llmhub` should become the default `LLM_PROVIDER` (the plan keeps `gemini` as the default).
