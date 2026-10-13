"""Small helpers for the Codex benchmark's conversational protocol."""

import re


def needs_checklist_approval(message: str) -> bool:
    text = message.lower()
    if "proceed" not in text or "checklist" not in text:
        return False
    if re.search(r"\byes\b", text) and any(word in text for word in ("unchecked", "paused", "reply", "yes/no")):
        return True
    if "implementation" in text and "unchecked" in text and ("explicit decision" in text or "please answer" in text):
        return True
    # Some spec-kit versions ask an open question without spelling out "yes".
    # The saved Codex summary retains only the tail of that message.
    return bool(
        re.search(r"(?:do you want me|would you like me|may i|shall i).*proceed", text, re.DOTALL)
        and "implementation" in text
    )
