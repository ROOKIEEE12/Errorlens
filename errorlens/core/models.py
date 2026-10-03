from __future__ import annotations
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    line: int
    text: str


class SuspectedFile(BaseModel):
    path: str
    line: int | None = None
    confidence: float = 0.5


class Risk(BaseModel):
    level: str  # low | medium | high | critical
    reason: str


class Context(BaseModel):
    platform: str = "unknown"      # vercel | github_actions | docker | local
    framework: str = "unknown"     # nextjs | python | ...
    package_manager: str | None = None


class Diagnosis(BaseModel):
    rule_id: str
    error_type: str
    title: str
    root_cause: str
    severity: str = "blocking"
    confidence: float
    context: Context
    evidence: list[Evidence]
    suspected_file: SuspectedFile | None = None
    cascade: list[Evidence] = Field(default_factory=list)
    fix_steps: list[str]
    verification_commands: list[str]
    risk: Risk
    fingerprint: str
    redaction_summary: dict[str, int] = Field(default_factory=dict)
    suggested_diff: str | None = None
    diff_note: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    related: list[dict] = Field(default_factory=list)
    ai: "Enrichment | None" = None


class Enrichment(BaseModel):
    """Optional LLM output. Validated against this schema; never replaces the deterministic diagnosis."""
    explanation_en: str
    explanation_hi: str = ""
    alternative_hypotheses: list[str] = Field(default_factory=list)
    risk_explanation: str = ""


Diagnosis.model_rebuild()
