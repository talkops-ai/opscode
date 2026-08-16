# Provider Credentials

> Add and manage API keys for model providers, Tavily web search, and LangSmith tracing.

OpsCode requires an API key for each model provider you utilize. The recommended way to configure credentials is the interactive [`/auth`](#use-auth-recommended) manager. For CI/CD and non-interactive environments, set [environment variables](#environment-variables-ci-and-headless) instead.

If the same key is set in multiple locations, see [Key resolution order](#key-resolution-order) for precedence rules.

For `.env` loading order and the `OPSCODE_` prefix, see [Configuration](./Configuration.md#environment-variables).

## Use `/auth` (recommended)

Open the credential manager from any interactive OpsCode session:

```
/auth
```

The credential manager lists installed LLM providers and indicates whether an active environment key is detected, surfaces providers available for configuration, and includes non-model services such as Tavily web search and LangSmith tracing. Select a provider to add or replace its key. Keys persist across sessions in `~/.opscode/.env`.

### Provider row labels

Each row shows the provider name followed by its source attribution:

| Label | Meaning |
|---|---|
| `[stored]` | A key saved persistently via `/auth` in `~/.opscode/.env` |
| `[env: VARNAME]` | The key comes from environment variable `VARNAME` (e.g., `OPSCODE_OPENAI_API_KEY` or `OPENAI_API_KEY`) |
| `[missing]` | No key is stored and the environment variable is unset; select the row to enter one |

The `/auth` prompt also provides an optional **base URL** field. Leave it blank to use the provider's default endpoint, or set a custom URL for private gateways, proxies, or enterprise VPC endpoints.

:::warning
A stored base URL is not classified as a secret and may be logged; the API key paired with it is always masked and never logged.
:::

## Supported providers

OpsCode supports 20 model providers out of the box:

| Provider | API Key Env Var | Base URL Env Var(s) |
|---|---|---|
| **Anthropic** | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_URL` |
| **OpenAI** | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, `OPENAI_API_BASE` |
| **Google GenAI** | `GOOGLE_API_KEY` | `GOOGLE_GEMINI_BASE_URL` |
| **Google Vertex AI** | `GOOGLE_CLOUD_PROJECT` | *(uses ADC, no key required)* |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` | `AZURE_OPENAI_ENDPOINT` |
| **Groq** | `GROQ_API_KEY` | `GROQ_BASE_URL`, `GROQ_API_BASE` |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_BASE` |
| **Together** | `TOGETHER_API_KEY` | `TOGETHER_API_BASE` |
| **Fireworks** | `FIREWORKS_API_KEY` | `FIREWORKS_BASE_URL`, `FIREWORKS_API_BASE` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `OPENROUTER_API_BASE` |
| **Mistral AI** | `MISTRAL_API_KEY` | `MISTRAL_BASE_URL` |
| **NVIDIA** | `NVIDIA_API_KEY` | `NVIDIA_BASE_URL` |
| **Perplexity** | `PPLX_API_KEY` | `PERPLEXITY_BASE_URL` |
| **Cohere** | `COHERE_API_KEY` | `CO_API_URL` |
| **IBM watsonx** | `WATSONX_APIKEY` | `WATSONX_URL` |
| **HuggingFace** | `HUGGINGFACEHUB_API_TOKEN` | `HF_INFERENCE_ENDPOINT` |
| **LiteLLM** | `LITELLM_API_KEY` | *(none)* |
| **xAI** | `XAI_API_KEY` | `XAI_API_BASE` |
| **Baseten** | `BASETEN_API_KEY` | `BASETEN_BASE_URL`, `BASETEN_API_BASE` |
| **Ollama** | *(optional)* `OLLAMA_API_KEY` | *(none — runs locally)* |

**Special cases:**

- **Google Vertex AI** uses Google Cloud Application Default Credentials (ADC). No API key is required — set `GOOGLE_CLOUD_PROJECT` instead.
- **Ollama** runs locally and does not require an API key by default. An optional key can be supplied via `OLLAMA_API_KEY`.

## Key resolution order

When OpsCode resolves an API key, the following sources are checked in order (first match wins):

1. **`OPSCODE_{KEY}`** — Prefixed environment variable (e.g., `OPSCODE_OPENAI_API_KEY`)
2. **Canonical env var** — Standard environment variable (e.g., `OPENAI_API_KEY`)
3. **`~/.opscode/.env`** — Global dotenv file
4. **`/auth` stored key** — Stored credential in `~/.opscode/.env` or `.state/auth.json`

The `OPSCODE_` prefix always takes highest precedence. This allows you to override a repository `.env` key in your shell without modifying files.

## Manage credentials from the shell

Use `opscode auth` subcommands for automated or scripted workflows:

```bash
# List configured credentials
opscode auth list

# Set a credential
opscode auth set openai

# Remove a credential
opscode auth remove openai
```

## Environment variables (CI and headless)

For CI/CD pipelines and non-interactive environments, export credentials directly:

```bash
export OPENAI_API_KEY="sk-..."
opscode -n "Validate the Terraform modules" --quiet
```

Or maintain a `~/.opscode/.env` file:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
LANGSMITH_API_KEY=ls-...
```

### Security

Keys in `~/.opscode/.env` and project `.env` are loaded at startup. OpsCode blocks sensitive system keys (`PATH`, `HOME`, `PYTHONPATH`, `LD_PRELOAD`, etc.) from being set via `.env` files to prevent environment tampering.

## Enable web search with Tavily

OpsCode uses [Tavily](https://tavily.com) for real-time web search. Add a key via `/auth` or set:

```bash
export TAVILY_API_KEY="tvly-..."
```

## Enable LangSmith tracing

Add your LangSmith API key via `/auth` or export:

```bash
export LANGSMITH_API_KEY="ls-..."
export LANGSMITH_PROJECT="opscode"  # optional, defaults to "opscode"
```

Tracing is automatically enabled on the next launch when a LangSmith key is detected.
