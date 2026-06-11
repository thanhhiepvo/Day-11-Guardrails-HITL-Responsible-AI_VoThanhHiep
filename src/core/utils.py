"""
Lab 11 — Helper Utilities
"""
import asyncio

from google.genai import types

try:
    from google.adk.models.google_llm import _ResourceExhaustedError
except ImportError:
    _ResourceExhaustedError = Exception


async def chat_with_agent(
    agent,
    runner,
    user_message: str,
    session_id=None,
    user_id="student",
    max_retries: int = 3,
):
    """Send a message to the agent and get the response.

    Args:
        agent: The LlmAgent instance
        runner: The InMemoryRunner instance
        user_message: Plain text message to send
        session_id: Optional session ID to continue a conversation
        user_id: User identifier (used by rate limiter and audit log)
        max_retries: Retries on API rate-limit / quota errors

    Returns:
        Tuple of (response_text, session)
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await _chat_with_agent_once(
                agent, runner, user_message, session_id, user_id
            )
        except _ResourceExhaustedError as exc:
            last_error = exc
            if attempt >= max_retries - 1:
                raise
            wait_seconds = 45 * (attempt + 1)
            print(
                f"  Gemini API limit reached — waiting {wait_seconds}s "
                f"before retry ({attempt + 1}/{max_retries - 1})..."
            )
            await asyncio.sleep(wait_seconds)

    raise last_error


async def _chat_with_agent_once(
    agent, runner, user_message: str, session_id=None, user_id="student"
):
    app_name = runner.app_name

    session = None
    if session_id is not None:
        try:
            session = await runner.session_service.get_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
        except (ValueError, KeyError):
            pass

    if session is None:
        try:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )
        except Exception:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=content
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_response += part.text

    return final_response, session
