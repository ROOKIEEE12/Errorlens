from pathlib import Path
import pytest
from errorlens.core.analyze import analyze_text

S = Path(__file__).parent.parent / "samples"
ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize("sample,etype", [
    ("next_cannot_read.log", "cannot_read_properties"),
    ("npm_eresolve.log", "dependency_conflict"),
    ("docker_copy.log", "docker_copy_failed"),
    ("gha_input.log", "gha_missing_input"),
    ("gha_invalid_workflow.log", "gha_invalid_workflow"),
    ("enoent.log", "file_not_found"),
    ("missing_script.log", "missing_npm_script"),
    ("prerender_only.log", "prerender_failure"),
])
def test_each_rule(sample, etype):
    d = analyze_text((S / sample).read_text())
    assert d.error_type == etype, d.title
    assert len(d.fix_steps) == 3


def test_prerender_is_not_root_when_real_error_exists():
    d = analyze_text((S / "next_cannot_read.log").read_text())
    assert "map" in d.title and d.suspected_file.path == "src/app/dashboard/page.tsx" and d.suspected_file.line == 18


def test_eresolve_flags_risk_high_even_though_steps_warn_about_force():
    d = analyze_text((S / "npm_eresolve.log").read_text())
    assert d.risk.level == "high"
    assert d.risk_flags == []          # our own "avoid --force" advice must not self-flag


def test_docker_location():
    d = analyze_text((S / "docker_copy.log").read_text())
    assert d.suspected_file.path == "Dockerfile" and d.suspected_file.line == 6 and d.context.platform == "docker"


def test_verified_diff_against_demo_repo():
    d = analyze_text((S / "vercel_module_not_found.log").read_text(), repo=ROOT / "demo" / "broken-nextjs")
    assert d.suggested_diff and '-import Header from "@/component/Header";' in d.suggested_diff
    assert '+import Header from "@/components/Header";' in d.suggested_diff
    assert "Verified" in d.diff_note


def test_no_diff_without_repo_but_hint_given():
    d = analyze_text((S / "vercel_module_not_found.log").read_text())
    assert d.suggested_diff is None and "--repo" in d.diff_note


def test_risk_scan_flags_unnegated_shortcuts():
    from errorlens.core.risk import scan
    assert scan(["npm install --legacy-peer-deps"]) and not scan(["Avoid --force as a fix"])
    assert scan(["typescript: { ignoreBuildErrors: true }"])
