"""Normalise volatile details so the same bug in different runs gets the same ID."""
from __future__ import annotations
import hashlib
import re

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TS = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b")
_HEX = re.compile(r"\b[0-9a-f]{12,}\b")
_ABS_PATH = re.compile(r"(?:/home/runner/work/[^/\s]+/[^/\s]+/|/vercel/path\d*/|/app/|/workspace/)")
_PORT = re.compile(r":\d{4,5}\b")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def normalize(text: str) -> str:
    text = strip_ansi(text)
    text = _TS.sub("<TS>", text)
    text = _UUID.sub("<UUID>", text)
    text = _HEX.sub("<HASH>", text)
    text = _ABS_PATH.sub("<ROOT>/", text)
    text = _PORT.sub(":<PORT>", text)
    return text.strip()


def make_fingerprint(framework: str, error_type: str, file_path: str | None, key: str) -> str:
    sig = "|".join([framework, error_type, normalize(file_path or "-"), normalize(key).lower()])
    return "EL-" + hashlib.sha256(sig.encode()).hexdigest()[:8].upper()
