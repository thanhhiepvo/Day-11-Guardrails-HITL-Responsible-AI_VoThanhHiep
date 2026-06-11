"""
Assignment 11 — Audit Log Plugin

Records every interaction (input, output, blocking layer, latency, judge scores).
Required for production compliance and post-incident forensics.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google.genai import types
from google.adk.plugins import base_plugin
from google.adk.agents.invocation_context import InvocationContext


class AuditLogPlugin(base_plugin.BasePlugin):
    """Log all pipeline interactions without blocking or modifying responses."""

    def __init__(self):
        super().__init__(name="audit_log")
        self.logs: list[dict] = []
        self._pending: dict[str, dict] = {}

    def _extract_text(self, content) -> str:
        if content is None:
            return ""
        text = ""
        if hasattr(content, "parts") and content.parts:
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
        elif isinstance(content, str):
            text = content
        return text

    def _user_id(self, invocation_context: InvocationContext | None) -> str:
        if invocation_context and getattr(invocation_context, "user_id", None):
            return invocation_context.user_id
        return "anonymous"

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> types.Content | None:
        user_id = self._user_id(invocation_context)
        self._pending[user_id] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "input": self._extract_text(user_message),
            "output": None,
            "blocked_by": None,
            "block_reason": None,
            "latency_ms": None,
            "judge_scores": None,
            "_start": time.time(),
        }
        return None

    async def after_model_callback(self, *, callback_context, llm_response):
        user_id = "anonymous"
        if callback_context and getattr(callback_context, "user_id", None):
            user_id = callback_context.user_id

        entry = self._pending.pop(user_id, None)
        if entry is None:
            return llm_response

        entry["output"] = self._extract_text(
            llm_response.content if hasattr(llm_response, "content") else llm_response
        )
        entry["latency_ms"] = round((time.time() - entry.pop("_start")) * 1000, 2)
        self.logs.append(entry)
        return llm_response

    def record_block(
        self,
        user_id: str,
        layer: str,
        reason: str,
        output: str | None = None,
        judge_scores: dict | None = None,
    ):
        """Finalize a log entry when a layer blocks before the main LLM runs."""
        entry = self._pending.pop(user_id, {})
        if not entry:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "input": "",
            }

        start = entry.pop("_start", time.time())
        entry["blocked_by"] = layer
        entry["block_reason"] = reason
        entry["output"] = output
        entry["latency_ms"] = round((time.time() - start) * 1000, 2)
        if judge_scores:
            entry["judge_scores"] = judge_scores
        self.logs.append(entry)

    def finalize_with_metadata(
        self,
        user_id: str,
        judge_scores: dict | None = None,
        blocked_by: str | None = None,
        block_reason: str | None = None,
    ):
        """Attach judge scores or output-layer block info to a completed entry."""
        entry = self._pending.get(user_id)
        if not entry:
            return
        if judge_scores:
            entry["judge_scores"] = judge_scores
        if blocked_by:
            entry["blocked_by"] = blocked_by
            entry["block_reason"] = block_reason

    def export_json(self, filepath: str | Path = "audit_log.json"):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2, default=str)
        return path
