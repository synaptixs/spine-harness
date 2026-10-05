"""Small helpers for the Codex benchmark's conversational protocol."""
import re


def needs_checklist_approval(message: str) -> bool:
    text = message.lower()
    return ("proceed" in text and "checklist" in text
            and bool(re.search(r"\byes\b", text))
            and any(word in text for word in ("unchecked", "paused", "reply", "yes/no")))
