# Model providers

> 20+ supported LLM providers with streaming, tool calling, and extended reasoning

OpsCode works with 20+ model providers. You can switch models mid-session without restarting, use different models for different subagents, and run fully offline with Ollama.

## Model format

Models are referenced using `provider:model-name`:

```
anthropic:claude-opus-4-7
openai:gpt-4.1
google_genai:gemini-2.5-pro
deepseek:deepseek-reasoner
ollama:llama3.3
```

You can set the model in several ways:

- **CLI flag:** `ops -M anthropic:claude-opus-4-7`
- **Persistent default:** `ops --default-model openai:gpt-4.1`
- **In-session:** `/model` (opens the picker) or `/model anthropic:claude-opus-4-7`
- **Config file:** Set `[model].default` in `~/.opscode/config.toml`
- **Subagent override:** Add `model: provider:model-name` in the subagent's `AGENTS.md` frontmatter

## Supported providers

| Provider | ID | Auth | Highlights |
|---|---|---|---|
| **Anthropic** | `anthropic` | `ANTHROPIC_API_KEY` | Claude 3.5/3.7, Extended Thinking, Vision |
| **OpenAI** | `openai` | `OPENAI_API_KEY` | GPT-4.1/4o, o1/o3-mini Reasoning, Vision |
| **Google GenAI** | `google_genai` | `GOOGLE_API_KEY` | Gemini 2.0/2.5 Pro/Flash, Flash Thinking |
| **Google Vertex AI** | `google_vertexai` | ADC (`GOOGLE_CLOUD_PROJECT`) | Enterprise Vertex AI endpoints |
| **Azure OpenAI** | `azure_openai` | `AZURE_OPENAI_API_KEY` | Azure-hosted OpenAI models |
| **Groq** | `groq` | `GROQ_API_KEY` | Ultra-low latency Llama, Qwen, DeepSeek |
| **DeepSeek** | `deepseek` | `DEEPSEEK_API_KEY` | DeepSeek V3, R1 Reasoning |
| **Together AI** | `together` | `TOGETHER_API_KEY` | Open-source foundation models |
| **Fireworks AI** | `fireworks` | `FIREWORKS_API_KEY` | High-speed function calling |
| **OpenRouter** | `openrouter` | `OPENROUTER_API_KEY` | Multi-provider routing gateway |
| **Mistral AI** | `mistralai` | `MISTRAL_API_KEY` | Mistral Large, Codestral, Pixtral |
| **NVIDIA NIM** | `nvidia` | `NVIDIA_API_KEY` | Accelerated NIM endpoints |
| **Perplexity** | `perplexity` | `PPLX_API_KEY` | Search-augmented Sonar models |
| **Cohere** | `cohere` | `COHERE_API_KEY` | Command R / R+ |
| **IBM watsonx** | `ibm` | `WATSONX_APIKEY` | Enterprise Granite and Llama |
| **HuggingFace** | `huggingface` | `HUGGINGFACEHUB_API_TOKEN` | Dedicated Inference Endpoints |
| **LiteLLM** | `litellm` | `LITELLM_API_KEY` | Unified proxy for internal gateways |
| **xAI** | `xai` | `XAI_API_KEY` | Grok 2 / Grok 3 |
| **Baseten** | `baseten` | `BASETEN_API_KEY` | Custom deployed models |
| **Ollama** | `ollama` | Optional | Fully local offline inference |

## Extended thinking

OpsCode supports extended reasoning for models like Claude 3.7 Thinking, OpenAI o1/o3-mini, and Gemini Flash Thinking. In the TUI, reasoning tokens are displayed in a collapsible thinking panel.

Set the reasoning effort:

```
/effort high       # Choices: low, medium, high
```

Or in `~/.opscode/config.toml`:

```toml
[model]
reasoning_effort = "high"
```

## Switch models

### In a session

```
/model                              # Open the model picker
/model anthropic:claude-opus-4-7    # Switch immediately
/fast                               # Jump to your configured fast model
/effort high                        # Adjust reasoning effort
```

### From the CLI

```bash
ops -M openai:gpt-4.1                           # One-time override
ops --default-model anthropic:claude-opus-4-7    # Set persistent default
ops --clear-default-model                        # Clear the default
```

OpsCode remembers your 10 most recently used models for quick access in the `/model` picker.

## Local models with Ollama

Run completely offline:

```bash
# Pull a model
ollama pull llama3.3

# Launch OpsCode with it
ops -M ollama:llama3.3
```

In `~/.opscode/config.toml`:

```toml
[providers.ollama]
enabled = true
base_url = "http://localhost:11434"
models = ["llama3.3", "qwen2.5-coder:32b"]
```
