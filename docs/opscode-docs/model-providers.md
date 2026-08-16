# Model Providers

> Supported LLM providers, model specifier format, extended reasoning, and provider configuration.

OpsCode works with 20+ LLM providers via LangChain and LangGraph integrations. It supports streaming responses, tool calling, reasoning/extended thinking, multimodal inputs, and runtime model hot-swapping without session restarts (via `ConfigurableModelMiddleware`).

---

## Model specifier format

Models are referenced across OpsCode using the standard `provider:model-name` format:

```
anthropic:claude-opus-4-7
openai:gpt-4.1
google_genai:gemini-2.5-pro
deepseek:deepseek-reasoner
groq:llama-3.3-70b-versatile
ollama:llama3.3
```

Use this format with:
- CLI flag: `opscode -M anthropic:claude-opus-4-7`
- Set persistent default: `opscode --default-model openai:gpt-4.1`
- Interactive slash command: `/model`
- `config.toml` default: `[model].default = "anthropic:claude-opus-4-7"`
- Subagent frontmatter: `model: anthropic:claude-haiku-4-5-20251001`

---

## Supported providers

| Provider | Provider ID | Authentication | Supported Features |
|---|---|---|---|
| **Anthropic** | `anthropic` | API Key (`ANTHROPIC_API_KEY`) | Claude 3.5/3.7, Extended Thinking, Vision, Tool Calling |
| **OpenAI** | `openai` | API Key (`OPENAI_API_KEY`) | GPT-4.1/4o, o1/o3-mini Reasoning, Tool Calling, Vision |
| **Google GenAI** | `google_genai` | API Key (`GOOGLE_API_KEY`) | Gemini 2.0/2.5 Pro/Flash, Flash Thinking, Multimodal |
| **Google Vertex AI** | `google_vertexai` | Google ADC (`GOOGLE_CLOUD_PROJECT`) | Enterprise Vertex AI Gemini endpoints |
| **Azure OpenAI** | `azure_openai` | API Key (`AZURE_OPENAI_API_KEY`) | Enterprise Azure-hosted OpenAI models |
| **Groq** | `groq` | API Key (`GROQ_API_KEY`) | Ultra-low latency Llama 3.3, Qwen, DeepSeek inference |
| **DeepSeek** | `deepseek` | API Key (`DEEPSEEK_API_KEY`) | DeepSeek V3, DeepSeek R1 Reasoning |
| **Together AI** | `together` | API Key (`TOGETHER_API_KEY`) | Open-source foundation models |
| **Fireworks AI** | `fireworks` | API Key (`FIREWORKS_API_KEY`) | High-speed function calling models |
| **OpenRouter** | `openrouter` | API Key (`OPENROUTER_API_KEY`) | Multi-provider unified routing gateway |
| **Mistral AI** | `mistralai` | API Key (`MISTRAL_API_KEY`) | Mistral Large, Codestral, Pixtral |
| **NVIDIA NIM** | `nvidia` | API Key (`NVIDIA_API_KEY`) | NVIDIA NIM accelerated endpoints |
| **Perplexity** | `perplexity` | API Key (`PPLX_API_KEY`) | Online search-augmented Sonar models |
| **Cohere** | `cohere` | API Key (`COHERE_API_KEY`) | Command R / Command R+ |
| **IBM watsonx** | `ibm` | API Key (`WATSONX_APIKEY`) | Enterprise Granite and Llama models |
| **HuggingFace** | `huggingface` | Token (`HUGGINGFACEHUB_API_TOKEN`) | Dedicated Inference Endpoints |
| **LiteLLM** | `litellm` | API Key (`LITELLM_API_KEY`) | Unified proxy for internal LLM gateways |
| **xAI** | `xai` | API Key (`XAI_API_KEY`) | Grok 2 / Grok 3 |
| **Baseten** | `baseten` | API Key (`BASETEN_API_KEY`) | Custom deployed open-source models |
| **Ollama** | `ollama` | Optional (`OLLAMA_API_KEY`) | Fully local offline inference (`localhost:11434`) |

---

## Reasoning & Extended Thinking

OpsCode natively supports extended reasoning tokens for models such as Claude 3.7 Thinking, OpenAI o1/o3-mini, and Gemini 2.0 Flash Thinking.

In the interactive TUI, reasoning streams are displayed inside a collapsible real-time thinking widget (`ThinkingStreamWidget`).

Set the reasoning effort level:

```bash
# In interactive mode:
/effort high       # Choices: low, medium, high

# In ~/.opscode/config.toml:
[model]
reasoning_effort = "high"
```

---

## Switching models

### Interactive TUI

```
/model                          # Open interactive model picker modal
/model anthropic:claude-opus-4-7  # Switch active model immediately
/fast                           # Switch to configured fast/cost-effective model
/effort high                    # Adjust reasoning effort
```

### CLI invocation

```bash
# Run single session with a specific model
opscode -M openai:gpt-4.1

# Set persistent default model in config.toml
opscode --default-model anthropic:claude-opus-4-7

# Clear configured default model
opscode --clear-default-model
```

### Recent model history

OpsCode maintains your 10 most recently used models in `~/.opscode/.state/recent_models.json` for instant access in the `/model` selector.

---

## Local models with Ollama

Run completely offline without cloud API keys:

```bash
# Pull model locally
ollama pull llama3.3
ollama pull qwen2.5-coder:32b

# Launch OpsCode with local model
opscode -M ollama:llama3.3
```

In `~/.opscode/config.toml`:

```toml
[providers.ollama]
enabled = true
base_url = "http://localhost:11434"
models = ["llama3.3", "qwen2.5-coder:32b"]
```
