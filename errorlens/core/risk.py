"""Fix-risk engine: flags shortcuts that hide problems. Negated mentions ("avoid --force") are ignored."""
from __future__ import annotations
import re

RISKY = {
    r"--force\b": "uses --force (can install conflicting/broken dependency trees)",
    r"--legacy-peer-deps": "uses --legacy-peer-deps (silences real peer conflicts)",
    r"ignoreBuildErrors": "disables Next.js build error checks",
    r"ignoreDuringBuilds": "disables lint checks during builds",
    r"skipLibCheck": "skips type checking of declaration files",
    r"(delete|remove|rm)\b[^\n]*(package-lock|pnpm-lock|yarn\.lock)": "deletes a lockfile (loses reproducible installs)",
    r"NEXT_PUBLIC_\w*(SECRET|TOKEN|PASSWORD|DATABASE|PRIVATE)": "puts a secret-looking value in a NEXT_PUBLIC_ variable (exposed to the browser)",
    r"chmod\s+777": "makes files world-writable",
}
_NEGATION = re.compile(r"\b(avoid|never|don'?t|do not|not|instead of|without)\b", re.I)
_ORDER = ["low", "medium", "high", "critical"]


def scan(texts: list[str]) -> list[str]:
    flags: list[str] = []
    for t in texts:
        for line in t.splitlines():
            if _NEGATION.search(line):
                continue
            for pat, why in RISKY.items():
                if re.search(pat, line, re.I) and why not in flags:
                    flags.append(why)
    return flags


def escalate(level: str, reason: str, flags: list[str]) -> tuple[str, str]:
    if not flags:
        return level, reason
    new = max(level, "high", key=_ORDER.index)
    return new, reason + " Risky shortcut detected: " + "; ".join(flags) + "."
