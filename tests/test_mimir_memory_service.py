"""Tests for MimirMemoryService against a fake Mimir MCP stdio server.

No real ``mimir`` binary is required: ``subprocess.Popen`` is monkeypatched to
return an in-process fake that speaks JSON-RPC 2.0 over fake stdin/stdout pipes
and models Mimir's recall OR-semantics, so these exercise the real RPC, async,
and tenant-isolation code paths.
"""

from __future__ import annotations

import asyncio
import json
import queue

import pytest

from google.genai import types
from google.adk.memory.memory_entry import MemoryEntry

import adk_mimir_memory.mimir_memory_service as svc_mod
from adk_mimir_memory import MimirMemoryService


# ── Fake Mimir MCP stdio server ────────────────────────────────────────────


class _FakeStdin:
    def __init__(self, on_line):
        self._on_line = on_line

    def write(self, s):
        for line in s.splitlines():
            if line.strip():
                self._on_line(line)

    def flush(self):
        pass

    def close(self):
        pass


class _FakeStdout:
    """Blocking, iterable line source fed by the fake server."""

    def __init__(self):
        self._q = queue.Queue()

    def put(self, line):
        self._q.put(line)

    def __iter__(self):
        return self

    def __next__(self):
        item = self._q.get()
        if item is None:
            raise StopIteration
        return item

    def close(self):
        self._q.put(None)


class FakeMimir:
    """Minimal Popen-compatible fake of the Mimir MCP stdio server.

    Options:
        answer_tools: if False, tools/call requests get no response (to test
            the RPC timeout).
        emit_notification_before_reply: if True, a JSON-RPC notification line is
            emitted before every tools/call reply (to test id correlation).
    """

    def __init__(self, *, answer_tools=True, emit_notification_before_reply=False):
        self.store = {}  # (category, key) -> arguments dict
        self.stdout = _FakeStdout()
        self.stdin = _FakeStdin(self._handle)
        self._alive = True
        self._answer_tools = answer_tools
        self._emit_notif = emit_notification_before_reply

    # --- JSON-RPC handling ---
    def _handle(self, line):
        req = json.loads(line)
        rid = req.get("id")
        method = req.get("method")
        if rid is None:
            return  # client notification, no response
        if method == "initialize":
            self._respond(rid, {"protocolVersion": "2024-11-05", "capabilities": {}})
            return
        if method == "tools/call":
            if not self._answer_tools:
                return  # simulate a hung server
            if self._emit_notif:
                self.stdout.put(
                    json.dumps(
                        {"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}
                    )
                    + "\n"
                )
            params = req["params"]
            name = params["name"]
            args = params["arguments"]
            if name == "mimir_remember":
                self.store[(args["category"], args["key"])] = args
                self._respond(rid, {"structuredContent": {"stored": True}})
            elif name == "mimir_recall":
                q = args.get("query", "").lower().split()
                cat = args.get("category")
                items = []
                for (c, _k), rec in self.store.items():
                    if cat and c != cat:
                        continue
                    body = rec["body_json"]
                    # Model Mimir's OR semantics: match if ANY query word appears.
                    if any(w in body.lower() for w in q):
                        items.append({"body_json": body, "created_at_unix_ms": 0})
                self._respond(rid, {"structuredContent": {"items": items}})
            else:
                self._respond(rid, {"structuredContent": {}})
            return
        self._respond(rid, {})

    def _respond(self, rid, result):
        self.stdout.put(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")

    # --- Popen surface ---
    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self._alive = False
        self.stdout.close()

    def kill(self):
        self._alive = False
        self.stdout.close()

    def wait(self, timeout=None):
        return 0


def _make_service(monkeypatch, tmp_path, **fake_kwargs):
    fake = FakeMimir(**fake_kwargs)
    monkeypatch.setattr(svc_mod.subprocess, "Popen", lambda *a, **k: fake)
    db = tmp_path / "mimir.db"
    # Use a platform-absolute path so __init__ skips the $PATH lookup.
    fake_bin = str(tmp_path / "fake-mimir")
    service = MimirMemoryService(
        db_path=str(db), mimir_binary=fake_bin, timeout_s=1.0
    )
    return service, fake


def _entry(text):
    return MemoryEntry(
        content=types.Content(role="user", parts=[types.Part.from_text(text=text)]),
        author="user",
        timestamp="2026-01-01T00:00:00+00:00",
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_init_completes_handshake(monkeypatch, tmp_path):
    service, _fake = _make_service(monkeypatch, tmp_path)
    assert service._request_id >= 1  # initialize consumed an id
    service._close()


def test_tenant_isolation_search(monkeypatch, tmp_path):
    """A search must never return another app's or user's memories, even though
    Mimir's recall OR-matches the shared query term."""
    service, _fake = _make_service(monkeypatch, tmp_path)

    asyncio.run(
        service.add_memory(
            app_name="app1", user_id="alice", memories=[_entry("alice likes turtles")]
        )
    )
    asyncio.run(
        service.add_memory(
            app_name="app1", user_id="bob", memories=[_entry("bob likes turtles")]
        )
    )
    asyncio.run(
        service.add_memory(
            app_name="app2", user_id="alice", memories=[_entry("alice in app2 turtles")]
        )
    )

    resp = asyncio.run(
        service.search_memory(app_name="app1", user_id="alice", query="turtles")
    )
    texts = [p.text for m in resp.memories for p in m.content.parts]
    assert texts == ["alice likes turtles"], texts  # only app1/alice
    service._close()


def test_rpc_timeout_when_server_hangs(monkeypatch, tmp_path):
    service, _fake = _make_service(monkeypatch, tmp_path, answer_tools=False)
    with pytest.raises(RuntimeError, match="timed out"):
        asyncio.run(
            service.search_memory(app_name="a", user_id="u", query="anything")
        )
    service._close()


def test_id_correlation_skips_notifications(monkeypatch, tmp_path):
    service, _fake = _make_service(
        monkeypatch, tmp_path, emit_notification_before_reply=True
    )
    asyncio.run(
        service.add_memory(
            app_name="app", user_id="u", memories=[_entry("hello world")]
        )
    )
    resp = asyncio.run(
        service.search_memory(app_name="app", user_id="u", query="hello")
    )
    texts = [p.text for m in resp.memories for p in m.content.parts]
    assert texts == ["hello world"], texts
    service._close()
