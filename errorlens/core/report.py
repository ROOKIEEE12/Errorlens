from __future__ import annotations
from .models import Diagnosis


def to_markdown(d: Diagnosis) -> str:
    """Share-safe report: built only from the already-redacted Diagnosis."""
    c = d.context
    out = ["# ErrorLens Diagnostic Report", "",
           f"**Fingerprint:** `{d.fingerprint}` · **Confidence:** {int(d.confidence*100)}% · **Stack:** {c.framework} / {c.platform}", "",
           "## Summary", d.root_cause, ""]
    if d.suspected_file:
        f = d.suspected_file
        out += ["## Probable location", f"`{f.path}" + (f":{f.line}" if f.line else "") + "`", ""]
    out += ["## Safe error excerpt", "```"] + [e.text for e in d.evidence] + ["```", "", "## Recommended action"]
    out += [f"{n}. {s}" for n, s in enumerate(d.fix_steps, 1)]
    if d.suggested_diff:
        out += ["", "## Suggested diff", "```diff", d.suggested_diff.rstrip(), "```"]
    if d.verification_commands:
        out += ["", "## Verify locally", "```bash"] + d.verification_commands + ["```"]
    out += ["", "## Risk", f"**{d.risk.level.upper()}** — {d.risk.reason}", ""]
    if d.ai:
        out += ["## AI explanation", d.ai.explanation_en, ""]
    n = sum(d.redaction_summary.values())
    out += ["## Security", f"{n} sensitive value(s) redacted before this report was generated." if n else "No sensitive values detected.", ""]
    return "\n".join(out)


def to_github_comment(d: Diagnosis) -> str:
    loc = ""
    if d.suspected_file:
        f = d.suspected_file
        loc = f"**Probable file:** `{f.path}" + (f":{f.line}" if f.line else "") + "`\n"
    steps = "\n".join(f"{n}. {s}" for n, s in enumerate(d.fix_steps, 1))
    ev = "\n".join(e.text for e in d.evidence)
    return (f"## ErrorLens diagnosis\n\n**Root cause:** {d.title} — {d.root_cause}\n{loc}"
            f"**Confidence:** {int(d.confidence*100)}% · **Fingerprint:** `{d.fingerprint}`\n\n**Fix:**\n{steps}\n\n"
            f"**Risk:** {d.risk.level.capitalize()} — {d.risk.reason}\n\n"
            f"<details>\n<summary>Safe diagnostic evidence</summary>\n\n```\n{ev}\n```\n</details>\n")


def to_text(d: Diagnosis) -> str:
    f = d.suspected_file
    lines = [f"{d.title} [{d.fingerprint}] ({int(d.confidence*100)}%)", d.root_cause]
    if f:
        lines.append(f"Location: {f.path}" + (f":{f.line}" if f.line else ""))
    lines += [f"{n}. {s}" for n, s in enumerate(d.fix_steps, 1)]
    lines.append(f"Risk: {d.risk.level} - {d.risk.reason}")
    return "\n".join(lines)


def render(d: Diagnosis, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt in ("markdown", "md"):
        return to_markdown(d)
    if fmt in ("github", "github-comment", "pr"):
        return to_github_comment(d)
    if fmt == "json":
        return d.model_dump_json(indent=2)
    if fmt in ("text", "txt"):
        return to_text(d)
    raise ValueError(f"unknown format '{fmt}' (markdown | github | json | text)")
