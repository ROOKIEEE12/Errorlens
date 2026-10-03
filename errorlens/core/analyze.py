from __future__ import annotations
import re
from pathlib import Path

from .detect import detect_context
from .diff import suggest_import_diff
from .fingerprint import make_fingerprint, strip_ansi
from .models import Diagnosis, Evidence, Risk
from .redact import redact
from .risk import escalate, scan
from .rules import CASCADE, RULES as BASE_RULES
from .rules_extra import EXTRA

ALL_RULES = BASE_RULES + EXTRA
_TS_PREFIX = re.compile(r"^\s*(?:\[\d{2}:\d{2}:\d{2}(?:\.\d+)?\]|\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s*")


def _clean(line: str) -> str:
    """Drop Vercel / GitHub timestamp prefixes for display; matching still runs on the original line."""
    return _TS_PREFIX.sub("", line).strip()


def _find_best(lines: list[str], pool, skip_cascade: bool):
    """First meaningful failure: earliest matching line wins; lower priority number breaks ties."""
    best = None  # (line_idx, priority, rule, match)
    for i, line in enumerate(lines):
        if skip_cascade and CASCADE.search(line):
            continue
        for rule in pool:
            m = rule.pattern.search(line)
            if m and (best is None or (i, rule.priority) < (best[0], best[1])):
                best = (i, rule.priority, rule, m)
        if best and best[0] == i:
            break
    return best


def analyze_text(raw: str, *, repo: str | Path | None = None, with_diff: bool = True) -> Diagnosis:
    """strip ANSI -> redact -> detect -> first meaningful failure -> rule -> (diff, risk scan)."""
    d, _ = analyze_with_log(raw, repo=repo, with_diff=with_diff)
    return d


def analyze_with_log(raw: str, *, repo: str | Path | None = None, with_diff: bool = True) -> tuple[Diagnosis, str]:
    """Same as analyze_text but also returns the redacted log (for UIs that highlight evidence lines)."""
    text, redactions = redact(strip_ansi(raw))
    lines = text.splitlines()
    ctx = detect_context(text)
    cascade = [Evidence(line=i + 1, text=_clean(l)) for i, l in enumerate(lines) if CASCADE.search(l)][:5]

    best = _find_best(lines, [r for r in ALL_RULES if not r.last_resort], True) \
        or _find_best(lines, [r for r in ALL_RULES if r.last_resort], False)
    if best is None:
        return _fallback(lines, ctx, cascade, redactions), text

    i, _, rule, m = best
    out = rule.build(lines, i, m, ctx)
    ev_end = i
    if isinstance(out, tuple):
        out, ev_end = out
    if out is None:
        return _fallback(lines, ctx, cascade, redactions), text

    if ctx.framework == "unknown" and rule.framework != "generic":
        ctx.framework = rule.framework
    if ctx.platform == "unknown" and rule.framework in ("docker", "github_actions"):
        ctx.platform = rule.framework
    evidence = [Evidence(line=k + 1, text=_clean(lines[k])) for k in range(i, min(ev_end, i + 6) + 1) if lines[k].strip()]
    fw = ctx.framework if ctx.framework != "unknown" else rule.framework

    diff, note = None, None
    if with_diff and out.error_type == "module_not_found" and out.file:
        if repo:
            diff, note = suggest_import_diff(Path(repo), out.file.path, m.group("module"))
        else:
            note = "Pass --repo <path> (CLI) to generate a verified diff for this import."

    flags = scan(out.fix_steps + out.verify + ([diff] if diff else []))
    level, reason = escalate(out.risk[0], out.risk[1], flags)

    return Diagnosis(
        rule_id=rule.id, error_type=out.error_type, title=out.title, root_cause=out.root_cause,
        confidence=out.confidence, context=ctx, evidence=evidence, suspected_file=out.file, cascade=cascade,
        fix_steps=out.fix_steps, verification_commands=out.verify, risk=Risk(level=level, reason=reason),
        fingerprint=make_fingerprint(fw, out.error_type, out.file.path if out.file else None, out.key),
        redaction_summary=redactions, suggested_diff=diff, diff_note=note, risk_flags=flags,
    ), text


def _fallback(lines, ctx, cascade, redactions) -> Diagnosis:
    pat = re.compile(r"\b(error|failed|fatal|exception)\b", re.I)
    idx = next((i for i, l in enumerate(lines) if pat.search(l) and not CASCADE.search(l)), None)
    ev = [Evidence(line=idx + 1, text=lines[idx].strip())] if idx is not None else []
    key = lines[idx] if idx is not None else "none"
    return Diagnosis(
        rule_id="generic.unclassified", error_type="unclassified", title="Unclassified failure",
        root_cause="No known rule matched. The earliest error-like line is shown as evidence; this is a low-confidence guess.",
        confidence=0.25, context=ctx, evidence=ev, cascade=cascade,
        fix_steps=["Read the evidence line and the ~10 lines above it for the first real failure.",
                   "Reproduce locally with the same command and Node/Python version as the failing environment.",
                   "If this error is common, add a rule for it in errorlens/core/rules_extra.py."],
        verification_commands=[], risk=Risk(level="low", reason="No change proposed."),
        fingerprint=make_fingerprint(ctx.framework, "unclassified", None, key), redaction_summary=redactions,
    )
