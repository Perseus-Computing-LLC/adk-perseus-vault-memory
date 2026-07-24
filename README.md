# ADK Perseus Vault Memory

> **📦 Package renamed.** Previously published on PyPI as [`adk-mimir-memory`](https://pypi.org/project/adk-mimir-memory/) (now archived). This project is now [`adk-perseus-vault-memory`](https://pypi.org/project/adk-perseus-vault-memory/) — install with `pip install adk-perseus-vault-memory`.

Persistent, local, encrypted cross-session memory for [Google ADK](https://github.com/google/adk-python) agents — backed by [Perseus Vault](https://github.com/Perseus-Computing-LLC/perseus-vault) .

## Why Perseus Vault?

| Backend | Dependencies | Encryption | Hybrid Search | Local |
|---|---|---|---|---|
| **InMemoryMemoryService** | None | ❌ | ❌ | ✅ |
| **VertexAiMemoryBankService** | GCP + Gemini | ❌ | Gemini-driven | ❌ |
| **VertexAiRagMemoryService** | GCP + RAG | ❌ | GCP vector | ❌ |
| **PerseusVaultMemoryService** | **Single binary** | **✅ AES-256** | **✅ BM25+FTS5+Dense** | **✅** |

- **Zero cloud dependencies** — a single Rust binary, SQLite database, fully local
- **AES-256-GCM encryption** at rest — your memory data stays private
- **Hybrid search** — BM25 keyword + FTS5 + dense vector search
- **30+ MCP tools** — remember, recall, synthesize, benchmark, federate, and more
- **Ebbinghaus confidence decay** — memories fade naturally, important ones persist

## Installation

```bash
pip install adk-perseus-vault-memory
```

This package requires the `perseus-vault` binary. Download it from:
https://github.com/Perseus-Computing-LLC/perseus-vault/releases

Or build from source:
```bash
cargo install perseus-vault
```

## Quick Start

```python
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from adk_perseus_vault_memory import PerseusVaultMemoryService

agent = Agent(
    name="my_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant with persistent memory.",
)

# The memory service is configured on the Runner, not on the Agent.
runner = Runner(
    agent=agent,
    app_name="my_app",
    session_service=InMemorySessionService(),
    memory_service=PerseusVaultMemoryService(db_path="~/.adk/vault.db"),
)
```

That's it. Sessions, events, and explicit memories are now persisted across restarts.

### Configuration

```python
# Custom database location
PerseusVaultMemoryService(db_path="/data/agent_memory.db")

# Custom perseus-vault binary path (if not on $PATH)
PerseusVaultMemoryService(vault_binary="/usr/local/bin/perseus-vault")

# Both
PerseusVaultMemoryService(
    db_path="/data/agent_memory.db",
    vault_binary="/usr/local/bin/perseus-vault",
)
```

## Perseus Live Context (Optional)

This package also includes a drop-in agent with live workspace awareness via [Perseus](https://github.com/Perseus-Computing-LLC/perseus):

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from adk_perseus_vault_memory.perseus_context import perseus_context_agent

# The agent resolves @file, @search, @memory directives at inference time.
# Bind it on the Runner; run_async takes no `agent` argument.
runner = Runner(
    agent=perseus_context_agent,
    app_name="my_app",
    session_service=InMemorySessionService(),
)
runner.run_async(
    user_id="user",
    session_id="session",
    new_message=types.Content(role="user", parts=[types.Part.from_text(
        text="What does the README say about deployment?"
    )]),
)
```

```bash
pip install adk-perseus-vault-memory[perseus]  # installs perseus-ctx
```

Set directives via session state:
```python
session = await runner.session_service.create_session(
    app_name="my_app",
    user_id="user",
    state={
        "_perseus_directives": "@file AGENTS.md @file README.md @memory deployment",
        "_perseus_workspace": "/path/to/project",
    },
)
```

## How It Works

```
┌─────────────┐     JSON-RPC (MCP stdio)     ┌────────────────┐
│  ADK Agent  │ ──────────────────────────▶  │  Perseus Vault │
│  (Python)   │ ◀──────────────────────────  │  (Rust)        │
└─────────────┘                              └───────┬────────┘
                                                      │
                                                 SQLite + FTS5
                                                 (AES-256-GCM)
```

The `PerseusVaultMemoryService` spawns a `perseus-vault` subprocess and communicates via JSON-RPC over stdin/stdout (MCP stdio transport). Each `add_session_to_memory`, `add_memory`, and `search_memory` call translates to a Perseus Vault MCP tool invocation.

## License

MIT — see [Perseus Vault](https://github.com/Perseus-Computing-LLC/perseus-vault) and [Perseus](https://github.com/Perseus-Computing-LLC/perseus) for the backing services.
