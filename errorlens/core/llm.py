"""Optional LLM enrichment. Receives ONLY structured, already-redacted facts — never the raw log.
The deterministic diagnosis stays the source of truth; the LLM adds explanation (EN + Hindi) and alternatives."""
from __future__ import annotations
import json
import os
import re
import urllib.request
from typing import Callable

from .models import Diagnosis, Enrichment
from .redact import redact

SYSTEM = (
    "You are ErrorLens, a debugging assistant. You get structured facts extracted from a failed build. "
    "Reply with ONLY a JSON object, no prose, no markdown fences, with keys: "
    "explanation_en (2-3 sentences, plain English), explanation_hi (same in simple Hinglish), "
    "alternative_hypotheses (array of up to 3 short strings), risk_explanation (1-2 sentences). "
    "Rules: do not propose disabling TypeScript or lint checks; do not suggest --force or --legacy-peer-deps; "
    "mark uncertain file paths as 'probable'; never invent file contents; do not repeat secrets."
)


def build_payload(d: Diagnosis) -> dict:
    return {
        "platform": d.context.platform, "framework": d.context.framework,
        "package_manager": d.context.package_manager, "error_type": d.error_type,
        "primary_error": [e.text for e in d.evidence][:6],
        "secondary_errors": [e.text for e in d.cascade][:3],
        "source_location": (f"{d.suspected_file.path}:{d.suspected_file.line}" if d.suspected_file else None),
        "baseline_root_cause": d.root_cause, "baseline_risk": d.risk.level,
    }


def _http_transport(system: str, user: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps({"model": os.environ.get("ERRORLENS_MODEL", "claude-sonnet-5-5"), "max_tokens": 700,
                       "system": system, "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def enrich(d: Diagnosis, transport: Callable[[str, str], str] | None = None) -> Enrichment | None:
    """Returns None on any failure (no key, network, bad JSON) — callers just skip the AI section."""
    payload, _ = redact(json.dumps(build_payload(d)))     # belt and braces: redact again before leaving the machine
    try:
        raw = (transport or _http_transport)(SYSTEM, payload)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        return Enrichment.model_validate(json.loads(raw))
    except Exception:
        return None
