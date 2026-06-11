"""
Assignment 11 Bonus — Session Anomaly Detector (6th safety layer)

Flags users who send multiple injection-like messages in one session,
catching multi-turn extraction attempts that single-message filters miss.
"""
from google.genai import types
from google.adk.plugins import base_plugin
from google.adk.agents.invocation_context import InvocationContext

from guardrails.input_guardrails import detect_injection_detail


class SessionAnomalyPlugin(base_plugin.BasePlugin):
    """Block sessions with repeated injection-like messages."""

    def __init__(self, max_injection_attempts: int = 2, audit_log=None):
        super().__init__(name="session_anomaly")
        self.max_injection_attempts = max_injection_attempts
        self.audit_log = audit_log
        self.session_counts: dict[str, int] = {}
        self.blocked_count = 0
        self.total_count = 0

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
        text = self._extract_text(user_message)
        is_injection, _ = detect_injection_detail(text)

        if is_injection:
            self.session_counts[user_id] = self.session_counts.get(user_id, 0) + 1

        if self.session_counts.get(user_id, 0) > self.max_injection_attempts:
            self.blocked_count += 1
            message = (
                "Your session has been flagged for suspicious activity. "
                "Please contact VinBank support if you need assistance."
            )
            if self.audit_log:
                self.audit_log.record_block(
                    user_id=user_id,
                    layer="session_anomaly",
                    reason=f"Exceeded {self.max_injection_attempts} injection attempts",
                    output=message,
                )
            return types.Content(
                role="model",
                parts=[types.Part.from_text(text=message)],
            )

        return None
