from pathlib import Path
from errorlens.core.analyze import analyze_text
from errorlens.core.fingerprint import make_fingerprint
from errorlens.core.redact import redact

S = Path(__file__).parent.parent / "samples"


def test_module_not_found_is_root_not_cascade():
    d = analyze_text((S / "vercel_module_not_found.log").read_text())
    assert d.error_type == "module_not_found"
    assert "@/component/Header" in d.root_cause
    assert d.suspected_file.path == "src/app/page.tsx" and d.suspected_file.line == 3
    assert d.context.platform == "vercel" and d.context.package_manager == "pnpm"
    assert len(d.fix_steps) == 3 and d.risk.level == "low"


def test_missing_env_and_redaction():
    d = analyze_text((S / "missing_env.log").read_text())
    assert d.error_type == "missing_environment_variable"
    assert d.suspected_file.path == "src/lib/db.ts"
    assert "url_credentials" in d.redaction_summary or "secret_assignment" in d.redaction_summary
    assert "hunter2pass" not in d.model_dump_json()
    assert "abcd1234efgh5678" not in d.model_dump_json()


def test_python_traceback():
    d = analyze_text((S / "py_traceback.log").read_text())
    assert d.error_type == "python_module_not_found"
    assert d.suspected_file.path.endswith("services/billing.py") and d.suspected_file.line == 2
    assert "pip install stripe" in " ".join(d.fix_steps)


def test_fingerprint_stable_across_runs():
    a = "Module not found: Can't resolve '@/x'\n" + "/home/runner/work/app-239/app-239/a.ts"
    b = a.replace("239", "456")
    assert analyze_text(a).fingerprint == analyze_text(b).fingerprint


def test_redact_jwt_and_bearer():
    t, c = redact("Authorization: Bearer abcdefghijklmnop12345\ntoken eyJhbGciOi.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4")
    assert "abcdefghijklmnop12345" not in t and "eyJzdWIiOiIx" not in t
