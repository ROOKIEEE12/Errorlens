from __future__ import annotations
import re
from .models import Context


def detect_context(text: str) -> Context:
    low = text.lower()
    platform = "unknown"
    if "vercel" in low or "▲" in text:
        platform = "vercel"
    elif "##[error]" in text or "##[group]" in text:
        platform = "github_actions"
    elif "failed to solve" in low or re.search(r"^Step \d+/\d+", text, re.M):
        platform = "docker"

    framework = "unknown"
    if "next.js" in low or "next build" in low or "next/" in low:
        framework = "nextjs"
    elif "traceback (most recent call last)" in low:
        framework = "python"

    pm = None
    for name in ("pnpm", "yarn", "npm"):
        if re.search(rf"\b{name}\b", low):
            pm = name
            break
    return Context(platform=platform, framework=framework, package_manager=pm)
