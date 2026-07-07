"""
Refusal detection engine.

Scans response text and metadata for signs that the model refused to comply.
"""

from __future__ import annotations

import re

# --- Refusal patterns (regex) ---
REFUSAL_PATTERNS = [
    r"I (?:cannot|can't|can not) (?:help|assist|provide|generate|create|do that)",
    r"I'm (?:sorry|afraid|unable|not able)",
    r"I apologize",
    r"As an AI(?: language model)?",
    r"I (?:must|have to) (?:decline|refuse|refrain)",
    r"(?:not|never) (?:appropriate|ethical|legal|safe)",
    r"against (?:my|the) (?:guidelines|policy|policies|programming|rules)",
    r"I (?:won't|will not|shouldn't|should not)",
    r"I don't think I should",
    r"content policy",
    r"safety (?:guidelines|policies|reasons|concerns)",
    r"(?:harmful|dangerous|illegal|unethical) (?:content|information|activities)",
    r"violat(?:es|ing) (?:the|my|our)",
    r"strongly advise against",
    r"unable to (?:provide|assist|help|generate|fulfill)",
    r"not (?:comfortable|willing|going to)",
    r"refrain from",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in REFUSAL_PATTERNS]


def detect_refusal_in_text(text: str) -> bool:
    """Check if text contains refusal language.

    Args:
        text: The response text to scan.

    Returns:
        True if refusal patterns are detected.
    """
    if not text or not text.strip():
        return False

    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True

    return False


def detect_refusal_openai(response_body: dict) -> bool:
    """Detect refusal in an OpenAI-format response."""
    # Check finish_reason
    choices = response_body.get("choices", [])
    for choice in choices:
        if choice.get("finish_reason") == "content_filter":
            return True
        # Check message content
        msg = choice.get("message", {}) or choice.get("delta", {})
        content = msg.get("content", "")
        if content and detect_refusal_in_text(content):
            return True

    return False


def detect_refusal_anthropic(response_body: dict) -> bool:
    """Detect refusal in an Anthropic Claude response."""
    # Claude returns stop_reason: "refusal" explicitly
    if response_body.get("stop_reason") == "refusal":
        return True

    # Also scan content blocks
    for block in response_body.get("content", []):
        if block.get("type") == "text":
            if detect_refusal_in_text(block.get("text", "")):
                return True

    return False


def detect_refusal_gemini(response_body: dict) -> bool:
    """Detect refusal in a Google Gemini response."""
    # Check prompt feedback for blocking
    feedback = response_body.get("promptFeedback", {})
    if feedback.get("blockReason"):
        return True

    # Check candidates
    for candidate in response_body.get("candidates", []):
        if candidate.get("finishReason") in ("SAFETY", "BLOCKED"):
            return True
        # Scan text parts
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text", "")
            if text and detect_refusal_in_text(text):
                return True

    return False
