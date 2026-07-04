"""ADK Perseus Vault Memory Service — persistent, local, encrypted cross-session memory.

Perseus Vault (github.com/Perseus-Computing-LLC/perseus-vault) is an
open-source (MIT) persistent memory engine with 30+ MCP tools, FTS5 + dense
hybrid search, and optional AES-256-GCM encryption. This service talks to the
Perseus Vault binary via JSON-RPC over stdin/stdout (MCP stdio transport).

Requirements:
    A ``perseus-vault`` binary must be on ``$PATH`` or passed explicitly via
    ``vault_binary``. Download from:
    https://github.com/Perseus-Computing-LLC/perseus-vault/releases
"""

from .perseus_vault_memory_service import PerseusVaultMemoryService

__all__ = ["PerseusVaultMemoryService"]
