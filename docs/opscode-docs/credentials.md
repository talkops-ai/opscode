# Provider credentials

> Set up API keys for model providers, web search, and tracing

OpsCode needs an API key for each model provider you want to use. The easiest way is the interactive `/auth` manager inside a session. For CI/CD, set environment variables instead.

## Use `/auth` (recommended)

Open the credential manager from any interactive session:

```
/auth
```

The manager shows all available providers and whether a key is configured. Select a provider to add or replace its key. Keys are saved to `~/.opscode/.env` and persist across sessions.

Each row shows the provider name with a status label:

| Label | Meaning |
|---|---|
| `[stored]` | Key saved via `/auth` |
| `[env: VARNAME]` | Key loaded from an environment variable |
| `[missing]` | No key found — select the row to add one |

You can also set a custom **base URL** for private gateways, proxies, or enterprise endpoints. Leave it blank to use the provider's default.

## Supported providers

OpsCode works with 20 providers out of the box:

| Provider | API Key Variable | Base URL Variable |
|---|---|---|
| **Anthropic** | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| **OpenAI** | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| **Google GenAI** | `GOOGLE_API_KEY` | `GOOGLE_GEMINI_BASE_URL` |
| **Google Vertex AI** | `GOOGLE_CLOUD_PROJECT` | *(uses Application Default Credentials)* |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` | `AZURE_OPENAI_ENDPOINT` |
| **Groq** | `GROQ_API_KEY` | `GROQ_BASE_URL` |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_BASE` |
| **Together** | `TOGETHER_API_KEY` | `TOGETHER_API_BASE` |
| **Fireworks** | `FIREWORKS_API_KEY` | `FIREWORKS_BASE_URL` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `OPENROUTER_API_BASE` |
| **Mistral AI** | `MISTRAL_API_KEY` | `MISTRAL_BASE_URL` |
| **NVIDIA** | `NVIDIA_API_KEY` | `NVIDIA_BASE_URL` |
| **Perplexity** | `PPLX_API_KEY` | `PERPLEXITY_BASE_URL` |
| **Cohere** | `COHERE_API_KEY` | `CO_API_URL` |
| **IBM watsonx** | `WATSONX_APIKEY` | `WATSONX_URL` |
| **HuggingFace** | `HUGGINGFACEHUB_API_TOKEN` | `HF_INFERENCE_ENDPOINT` |
| **LiteLLM** | `LITELLM_API_KEY` | — |
| **xAI** | `XAI_API_KEY` | `XAI_API_BASE` |
| **Baseten** | `BASETEN_API_KEY` | `BASETEN_BASE_URL` |
| **Ollama** | *(optional)* `OLLAMA_API_KEY` | *(runs locally)* |

**Special cases:**
- **Vertex AI** uses Google Cloud Application Default Credentials — no API key needed, just set `GOOGLE_CLOUD_PROJECT`.
- **Ollama** runs locally and doesn't require a key by default.

## Key resolution order

When multiple sources have the same key, OpsCode uses the first match:

1. **`OPSCODE_{KEY}`** — Prefixed env var (e.g., `OPSCODE_OPENAI_API_KEY`) — always wins
2. **Standard env var** — e.g., `OPENAI_API_KEY`
3. **`~/.opscode/.env`** — Global dotenv file
4. **`/auth` stored key** — Credential saved via the auth manager

The `OPSCODE_` prefix lets you override any key from your shell without modifying files.

## Manage credentials from the command line

Use `ops auth` for scripted workflows:

```bash
# List configured credentials
ops auth list

# Set a credential
ops auth set openai

# Remove a credential
ops auth remove openai
```

## Environment variables (CI/CD)

For non-interactive environments, export credentials directly:

```bash
export OPENAI_API_KEY="sk-..."
ops -n "Validate the Terraform modules" --quiet
```

Or maintain a `~/.opscode/.env` file:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
LANGSMITH_API_KEY=ls-...
```

OpsCode blocks sensitive system variables (`PATH`, `HOME`, `PYTHONPATH`) from being set via `.env` files to prevent environment tampering.

## Web search

OpsCode uses [Tavily](https://tavily.com) for web search. Add a key via `/auth` or:

```bash
export TAVILY_API_KEY="tvly-..."
```

## LangSmith tracing

Add your LangSmith key via `/auth` or:

```bash
export LANGSMITH_API_KEY="ls-..."
export LANGSMITH_PROJECT="opscode"  # optional, defaults to "opscode"
```

Tracing starts automatically on the next launch when a LangSmith key is detected.
