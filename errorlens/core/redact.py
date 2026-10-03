"""Local secret redaction. Always runs BEFORE parsing, storage, or any AI call."""
from __future__ import annotations
import re

# (name, compiled regex, replacement). Order matters: specific -> generic.
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED PRIVATE KEY]"),
    ("url_credentials", re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^\s:/@]+:[^\s@/]+@"), r"\g<scheme>[REDACTED]@"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\b"), "[REDACTED JWT]"),
    ("bearer_token", re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/\-]{8,}=*"), r"\1 [REDACTED]"),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED GITHUB TOKEN]"),
    ("api_key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}\b"), "[REDACTED API KEY]"),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED AWS KEY]"),
    # Contextual: KEY_NAME=value where the name looks sensitive
    ("secret_assignment", re.compile(
        r"(?i)\b(?P<name>[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY)[A-Z0-9_]*)(?P<sep>\s*[=:]\s*)(?P<val>[^\s'\"]{6,})"),
     r"\g<name>\g<sep>[REDACTED]"),
]


def _pem_repl(m: re.Match) -> str:
    # keep the same number of lines so evidence line numbers still match the original log
    return "[REDACTED PRIVATE KEY]" + "\n" * m.group(0).count("\n")


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (safe_text, {type: count}). Line count is preserved."""
    counts: dict[str, int] = {}
    for name, pattern, repl in _PATTERNS:
        text, n = pattern.subn(_pem_repl if name == "private_key" else repl, text)
        if n:
            counts[name] = counts.get(name, 0) + n
    return text, counts
