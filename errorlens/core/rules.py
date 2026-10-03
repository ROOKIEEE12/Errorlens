"""Deterministic error rules. Each rule finds a root-cause line and builds a baseline diagnosis.

To add a rule: write a function (lines, i, match, ctx) -> RuleResult and register it in RULES.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable

from .models import Context, SuspectedFile

# Lines that are consequences, never the root cause.
CASCADE = re.compile(
    r"(ELIFECYCLE|Command .* exited with|exit code [1-9]|Deployment failed|Build failed|"
    r"npm ERR! (code|path|command)|ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL|Error: Process completed with exit code|"
    r"failed to solve: process .* did not complete successfully|Build failed because of webpack errors|"
    r"Export encountered errors|Next\.js build worker exited)", re.I)

_FILE_LOC = re.compile(r"(?P<path>(?:\./|/)?(?:[\w@.\-\[\]()]+/)*[\w@.\-\[\]()]+\.(?:tsx?|jsx?|mjs|cjs|py))(?::(?P<line>\d+))?")


@dataclass
class RuleResult:
    error_type: str
    title: str
    root_cause: str
    fix_steps: list[str]
    verify: list[str]
    risk: tuple[str, str]
    confidence: float
    key: str                       # stable bit used for the fingerprint
    file: SuspectedFile | None = None


@dataclass
class Rule:
    id: str
    framework: str
    pattern: re.Pattern
    build: Callable[[list[str], int, re.Match, Context], RuleResult]
    priority: int = 50
    last_resort: bool = False   # only used when nothing else matched


_ROOT_PREFIX = re.compile(r"^(?:/vercel/path\d*/|/home/runner/work/[^/]+/[^/]+/|/github/workspace/|/app/|/workspace/|\./)")
_BUILD_OUTPUT = re.compile(r"(?:^|/)(?:node_modules|\.next|dist|build|out)/")


def _find_file(lines: list[str], i: int, before: int = 4, after: int = 4) -> SuspectedFile | None:
    """Look near the error line for a SOURCE path (`./src/app/page.tsx:3:1`, `at src/lib/db.ts:12:11`).
    Build output (.next/, dist/, node_modules/) is skipped; CI root prefixes are stripped."""
    order = [i] + [i + d for d in range(1, after + 1)] + [i - d for d in range(1, before + 1)]
    for j in order:
        if not 0 <= j < len(lines):
            continue
        for m in _FILE_LOC.finditer(lines[j]):
            path = _ROOT_PREFIX.sub("", m.group("path"))
            if _BUILD_OUTPUT.search(path):
                continue
            return SuspectedFile(path=path, line=int(m.group("line")) if m.group("line") else None,
                                 confidence=0.8 if j == i else 0.65)
    return None


def _build_cmd(ctx: Context) -> str:
    return {"pnpm": "pnpm build", "yarn": "yarn build"}.get(ctx.package_manager or "", "npm run build")


# ---------- Next.js ----------
def _module_not_found(lines, i, m, ctx):
    mod = m.group("module")
    alias = mod.startswith("@/")
    return RuleResult(
        error_type="module_not_found",
        title="Module cannot be resolved",
        root_cause=f"The build cannot resolve the import '{mod}'. The file is missing, misnamed (check casing — Linux is case-sensitive), or the path alias is not configured.",
        fix_steps=[
            f"Confirm a file for '{mod}' exists at the expected path and that its filename casing matches the import exactly.",
            "Correct the import path in the importing file" + (" and verify the '@/*' mapping under 'paths' in tsconfig.json." if alias else "; if it is an npm package, install it as a dependency."),
            f"Clear the cache and rebuild locally to confirm.",
        ],
        verify=["rm -rf .next", f"{ctx.package_manager or 'npm'} install" if ctx.package_manager != "npm" else "npm ci", _build_cmd(ctx)],
        risk=("low", "Only changes an import path or filename; behaviour is unchanged."),
        confidence=0.9, key=mod, file=_find_file(lines, i),
    )


def _missing_env(lines, i, m, ctx):
    var = m.group("var")
    public = var.startswith("NEXT_PUBLIC_")
    return RuleResult(
        error_type="missing_environment_variable",
        title=f"Missing environment variable {var}",
        root_cause=f"{var} is not available in the build environment, and code reads/validates it at import or build time.",
        fix_steps=[
            f"Add {var} in your host's Environment Variables (Vercel: Project Settings → Environment Variables) for Production and Preview.",
            "Confirm the name matches exactly, including case, and that it is not scoped to a different environment." + (" Note: NEXT_PUBLIC_ values are bundled into client code." if public else ""),
            "Redeploy (or rebuild locally with the variable set) to verify.",
        ],
        verify=[f"{var}=<value> {_build_cmd(ctx)}"],
        risk=("medium", "Fixes the build but changes configuration. " + (
            "NEXT_PUBLIC_ variables are exposed to the browser — never put secrets or database URLs in them."
            if public else "Do not weaken the check just to make the build pass; runtime calls will fail if the value is truly absent.")),
        confidence=0.92, key=var, file=_find_file(lines, i),
    )


def _ts_error(lines, i, m, ctx):
    msg = m.group("msg").strip()
    return RuleResult(
        error_type="typescript_type_error",
        title="TypeScript type error",
        root_cause=f"The TypeScript compiler rejected the code: {msg}",
        fix_steps=[
            "Open the reported file and line and read the full type error, including the 'Type X is not assignable to type Y' detail lines.",
            "Fix the type at its source (correct the value, widen/narrow the type, or add the missing property) rather than casting with 'any'.",
            "Run the type checker locally until it passes.",
        ],
        verify=["npx tsc --noEmit", _build_cmd(ctx)],
        risk=("low", "Type-only change in most cases. Avoid 'ignoreBuildErrors' or 'skipLibCheck' as a shortcut — they hide real problems."),
        confidence=0.8, key=re.sub(r"'[^']*'", "'X'", msg), file=_find_file(lines, i),
    )


# ---------- Python ----------
def _py_traceback(lines, i, m, ctx):
    """`i` is the 'Traceback' line. Root = final exception line; frame = last File line before it."""
    exc_re = re.compile(r"^(?P<exc>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Warning)):?\s*(?P<msg>.*)$")
    exc_idx, exc = None, None
    for j in range(i + 1, len(lines)):
        mm = exc_re.match(lines[j])
        if mm and not lines[j].startswith(" "):
            exc_idx, exc = j, mm
            break
    if exc is None:
        return None
    frame = None
    for j in range(exc_idx - 1, i, -1):
        fm = re.search(r'File "(?P<p>[^"]+)", line (?P<l>\d+)', lines[j])
        if fm and "site-packages" not in fm.group("p"):
            frame = SuspectedFile(path=fm.group("p"), line=int(fm.group("l")), confidence=0.85)
            break
    name, msg = exc.group("exc"), exc.group("msg")
    mod = re.search(r"No module named '([^']+)'", msg)
    if name == "ModuleNotFoundError" and mod:
        pkg = mod.group(1).split(".")[0]
        return RuleResult(
            error_type="python_module_not_found", title=f"Missing Python module '{pkg}'",
            root_cause=f"Python cannot import '{mod.group(1)}'. It is not installed in the active environment, or the wrong interpreter/venv is being used.",
            fix_steps=[
                "Activate the project's virtual environment and confirm with 'which python' / 'python -c \"import sys; print(sys.executable)\"'.",
                f"Install the dependency: pip install {pkg} (and add it to requirements.txt / pyproject.toml).",
                "Re-run the failing command.",
            ],
            verify=[f'python -c "import {pkg}"', "python -m pytest -q"],
            risk=("low", "Adds a dependency. Pin the version and check the package name — the import name can differ from the PyPI name."),
            confidence=0.9, key=mod.group(1), file=frame), exc_idx
    return RuleResult(
        error_type=f"python_{name.lower()}", title=f"{name}",
        root_cause=f"{name}: {msg}" if msg else name,
        fix_steps=[
            "Go to the last project frame in the traceback (shown as the suspected file) and inspect the values involved at that line.",
            "Handle or correct the offending value (validate input, check keys/attributes/types before use).",
            "Add a test that reproduces this input and re-run the suite.",
        ],
        verify=["python -m pytest -q"],
        risk=("low", "Localized code change; confirm with a regression test."),
        confidence=0.75, key=f"{name}:{re.sub(r'[0-9]+', 'N', msg)}", file=frame), exc_idx


RULES: list[Rule] = [
    Rule("nextjs.module_not_found", "nextjs", re.compile(r"(?:Module not found: )?Can't resolve ['\"](?P<module>[^'\"]+)['\"]"), _module_not_found, 10),
    Rule("env.missing_variable", "generic", re.compile(r"(?:Missing|Undefined|Invalid)(?: required)? environment variable:?\s*[`'\"]?(?P<var>[A-Z][A-Z0-9_]+)"), _missing_env, 10),
    Rule("typescript.type_error", "nextjs", re.compile(r"Type error:\s*(?P<msg>.+)"), _ts_error, 20),
    Rule("python.traceback", "python", re.compile(r"Traceback \(most recent call last\):"), _py_traceback, 15),
]
