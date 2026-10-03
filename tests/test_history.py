from pathlib import Path
from typer.testing import CliRunner
from errorlens.cli import app

S = Path(__file__).parent.parent / "samples"
r = CliRunner()


def test_history_counts_and_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("ERRORLENS_HOME", str(tmp_path))
    log = str(S / "vercel_module_not_found.log")
    r.invoke(app, ["analyze", log])
    out = r.invoke(app, ["analyze", log]).output
    assert "Recurring" in out and "2x" in out
    fp = r.invoke(app, ["fingerprint", log]).output.strip()
    r.invoke(app, ["history", "resolve", fp, "Fix alias in tsconfig"])
    assert "Known resolution" in r.invoke(app, ["analyze", log]).output
    assert fp in r.invoke(app, ["history", "search", "resolve"]).output


def test_report_has_no_secrets():
    out = r.invoke(app, ["report", str(S / "missing_env.log")]).output
    assert "hunter2pass" not in out and "## Security" in out


def test_cli_formats_repo_and_screenshot(tmp_path, monkeypatch):
    monkeypatch.setenv("ERRORLENS_HOME", str(tmp_path))
    demo = S.parent / "demo" / "broken-nextjs"
    out = r.invoke(app, ["analyze", str(S / "vercel_module_not_found.log"), "--repo", str(demo), "--no-save"]).output
    assert "Suggested diff" in out and "components/Header" in out
    assert "ErrorLens diagnosis" in r.invoke(app, ["report", str(S / "docker_copy.log"), "-f", "github"]).output
    assert r.invoke(app, ["report", str(S / "docker_copy.log"), "-f", "nope"]).exit_code == 2
    import json
    j = json.loads(r.invoke(app, ["analyze", str(S / "npm_eresolve.log"), "--json", "--no-save"]).output)
    assert j["error_type"] == "dependency_conflict"
