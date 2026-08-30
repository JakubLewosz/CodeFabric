"""Small helpers shared by agent nodes."""

import re
from typing import Any, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

_DECISION_RE = re.compile(
    r"^\s*(?:[#>*_-]+\s*)?(?:\*\*)?(APPROVE|REJECT)(?:\*\*)?"
    r"(?=\s|:|$)[\s:-]*",
    re.IGNORECASE,
)


def extract_text_content(value: Any) -> str:
    """Return plain text from common LangChain response content shapes."""
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


def normalize_messages(messages: Any) -> List[BaseMessage]:
    """Coerce persisted or hand-written messages into LangChain messages."""
    if not messages:
        return []
    if not isinstance(messages, (list, tuple)):
        messages = [messages]

    normalized: List[BaseMessage] = []
    for message in messages:
        if isinstance(message, BaseMessage):
            normalized.append(message)
            continue
        if isinstance(message, dict):
            content = extract_text_content(message.get("content", ""))
            role = str(message.get("role", message.get("type", "user"))).lower()
            if role in {"assistant", "ai"}:
                normalized.append(AIMessage(content=content))
            elif role == "system":
                normalized.append(SystemMessage(content=content))
            else:
                normalized.append(HumanMessage(content=content))
            continue
        normalized.append(HumanMessage(content=extract_text_content(message)))
    return normalized


def review_decision(feedback: Any) -> Optional[str]:
    """Parse a leading, standalone APPROVE/REJECT marker."""
    text = extract_text_content(feedback)
    match = _DECISION_RE.match(text)
    return match.group(1).upper() if match else None


def canonical_review(feedback: Any) -> Optional[str]:
    """Normalize a valid review while retaining its explanatory body."""
    text = extract_text_content(feedback).strip()
    match = _DECISION_RE.match(text)
    if not match:
        return None
    decision = match.group(1).upper()
    body = text[match.end() :].strip()
    return f"{decision}: {body}" if body else f"{decision}: Brak uzasadnienia."
