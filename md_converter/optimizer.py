from __future__ import annotations
import re
from enum import Enum

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
    _TIKTOKEN_AVAILABLE = True
except Exception:
    _TIKTOKEN_AVAILABLE = False


class Mode(Enum):
    FIDELITY = "fidelity"
    COMPACT = "compact"


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base (GPT-4 tokenizer)."""
    if _TIKTOKEN_AVAILABLE:
        return len(_ENC.encode(text))
    # Rough fallback: ~4 chars per token
    return max(1, len(text) // 4)


def optimize(text: str, mode: Mode = Mode.FIDELITY) -> str:
    """Apply token optimization. Fidelity preserves structure; compact compresses."""
    if mode == Mode.FIDELITY:
        return _optimize_fidelity(text)
    return _optimize_compact(text)


def _normalize_whitespace(text: str) -> str:
    """Collapse intra-line multiple spaces, normalize line endings."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        # Preserve leading spaces (indentation), collapse internal multiple spaces
        stripped_left = line.lstrip(" ")
        indent = len(line) - len(stripped_left)
        collapsed = re.sub(r" {2,}", " ", stripped_left)
        lines.append(" " * indent + collapsed)
    return "\n".join(lines)


def _optimize_fidelity(text: str) -> str:
    """Light cleanup: normalize whitespace, collapse excessive blank lines."""
    text = _normalize_whitespace(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _optimize_compact(text: str) -> str:
    """Aggressive cleanup: collapse blank lines, remove between list items, trim lines."""
    text = _normalize_whitespace(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove blank lines between consecutive list items
    text = re.sub(r"(^[-*\d].*)\n\n([-*\d])", r"\1\n\2", text, flags=re.MULTILINE)
    # Trim trailing spaces from each line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip() + "\n"
