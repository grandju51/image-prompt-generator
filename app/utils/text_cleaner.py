from typing import List


def apply_markers(text: str, markers: List[str]) -> str:
    """Return the text that comes after the first matching marker.

    Iterates markers in order; stops at the first one found in the text.
    The marker itself is consumed; leading whitespace/newlines are stripped.
    """
    for raw in markers:
        marker = raw.strip()
        if not marker:
            continue
        idx = text.find(marker)
        if idx != -1:
            return text[idx + len(marker):].lstrip("\n").strip()
    return text
