"""
Assignment 11 — Rate Limiter Plugin

Sliding-window rate limiter per user. Blocks abuse before any LLM call,
catching volumetric attacks that other content-based guardrails miss.
"""
import time
from collections import defaultdict, deque

from google.genai import types
from google.adk.plugins import base_plugin
from google.adk.agents.invocation_context import InvocationContext


class RateLimitPlugin(base_plugin.BasePlugin):
    """Block users who exceed max_requests within a sliding time window."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60, audit_log=None):
        super().__init__(name="rate_limiter")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_windows: dict[str, deque] = defaultdict(deque)
        self.blocked_count = 0
        self.total_count = 0
        self.audit_log = audit_log

    def _extract_text(self, content: types.Content) -> str:
        text = ""
        if content and content.parts:
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
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
        self.total_count += 1
        user_id = self._user_id(invocation_context)
        now = time.time()
        window = self.user_windows[user_id]

        while window and window[0] <= now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            self.blocked_count += 1
            wait_seconds = int(self.window_seconds - (now - window[0])) + 1
            message = (
                f"Rate limit exceeded. Please wait {wait_seconds} seconds "
                f"before sending more requests."
            )
            if self.audit_log:
                self.audit_log.record_block(
                    user_id=user_id,
                    layer="rate_limiter",
                    reason=f"Exceeded {self.max_requests} requests per {self.window_seconds}s",
                    output=message,
                )
            return types.Content(
                role="model",
                parts=[types.Part.from_text(text=message)],
            )

        window.append(now)
        return None
