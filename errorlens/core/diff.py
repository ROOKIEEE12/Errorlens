"""Repo-aware unified diff for import-path typos. Only runs when the user points at a repo."""
from __future__ import annotations
import difflib
import os
import re
from pathlib import Path

_SKIP = {"node_modules", ".next", ".git", "dist", "build", ".venv", "__pycache__"}
_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _candidate_specs(repo: Path, importer: Path, module: str) -> dict[str, Path]:
    specs: dict[str, Path] = {}
    base = repo / "src" if (repo / "src").is_dir() else repo
    for p in repo.rglob("*"):
        if p.suffix not in _EXT or any(part in _SKIP for part in p.parts):
            continue
        stem = p.with_suffix("")
        if stem.name == "index":
            stem = stem.parent
        if module.startswith("@/"):
            try:
                specs["@/" + stem.relative_to(base).as_posix()] = p
            except ValueError:
                continue
        elif module.startswith("."):
            try:
                r = os.path.relpath(stem, importer.parent).replace("\\", "/")
                specs[r if r.startswith(".") else "./" + r] = p
            except ValueError:
                continue
    return specs


def suggest_import_diff(repo: Path, rel_file: str, module: str) -> tuple[str | None, str]:
    """Return (unified_diff | None, note)."""
    importer = repo / rel_file
    if not importer.is_file():
        return None, f"Could not find {rel_file} in the repo, so no diff was generated."
    specs = _candidate_specs(repo, importer, module)
    if not specs:
        return None, "Only alias (@/…) and relative imports are supported for diffs."
    lower = {k.lower(): k for k in specs}
    best = lower.get(module.lower())
    if not best:
        close = difflib.get_close_matches(module, list(specs), n=1, cutoff=0.8)
        best = close[0] if close else None
    if not best or best == module:
        return None, "No close matching file found in the repo — fix the import manually."
    old = importer.read_text().splitlines(keepends=True)
    new = [l.replace(module, best) if re.search(rf"['\"]{re.escape(module)}['\"]", l) else l for l in old]
    if old == new:
        return None, "The failing import line was not found in the file."
    rel = Path(rel_file).as_posix()
    diff = "".join(difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}", n=2))
    return diff, f"Verified against repo: '{best}' exists ({specs[best].relative_to(repo).as_posix()}). Review before applying."
