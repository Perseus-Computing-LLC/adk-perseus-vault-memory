"""ADK Mimir Memory Service — persistent, local, encrypted cross-session memory.

Mimir (github.com/Perseus-Computing-LLC/mimir) is an open-source (MIT)
persistent memory engine with 30+ MCP tools, FTS5 + dense hybrid search,
and optional AES-256-GCM encryption. This service talks to the Mimir
binary via JSON-RPC over stdin/stdout (MCP stdio transport).

Requirements:
    A ``mimir`` binary must be on ``$PATH`` or passed explicitly via
    ``mimir_binary``. Download from:
    https://github.com/Perseus-Computing-LLC/mimir/releases
"""

from .mimir_memory_service import MimirMemoryService

__all__ = ["MimirMemoryService"]
