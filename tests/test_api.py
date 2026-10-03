import io
from pathlib import Path
from fastapi.testclient import TestClient
from errorlens.api.main import app

S = Path(__file__).parent.parent / "samples"
c = TestClient(app)


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("ERRORLENS_HOME", str(tmp_path))


def test_analyze_text_and_privacy(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    r = c.post("/v1/analyze", data={"text": (S / "missing_env.log").read_text()})
    j = r.json()
    assert r.status_code == 200 and j["diagnosis"]["error_type"] == "missing_environment_variable"
    assert "hunter2pass" not in r.text and j["privacy"]["raw_log_stored"] is False
    assert j["recurrence"]["count"] == 1
    assert c.post("/v1/analyze", data={"text": (S / "missing_env.log").read_text()}).json()["recurrence"]["count"] == 2


def test_file_upload_and_validation(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    f = {"file": ("build.log", (S / "npm_eresolve.log").read_bytes(), "text/plain")}
    assert c.post("/v1/analyze", files=f).json()["diagnosis"]["risk"]["level"] == "high"
    assert c.post("/v1/analyze").status_code == 400


def test_ai_unavailable_is_graceful(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    j = c.post("/v1/analyze", data={"text": "Module not found: Can't resolve '@/x'", "privacy_mode": "sanitized_ai"}).json()
    assert j["ai_status"].startswith("unavailable") and j["diagnosis"]["ai"] is None


def test_repo_path_blocked_by_default(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    r = c.post("/v1/analyze", data={"text": "x", "repo_path": "/etc"})
    assert r.status_code == 403


def test_safe_report_and_history(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    r = c.post("/v1/reports/safe", json={"text": (S / "missing_env.log").read_text(), "format": "github"}).json()
    assert "ErrorLens diagnosis" in r["report"] and "hunter2pass" not in r["report"]
    c.post("/v1/analyze", data={"text": (S / "enoent.log").read_text()})
    items = c.get("/v1/history").json()["items"]
    assert items
    fp = items[0]["fingerprint"]
    assert c.post(f"/v1/history/{fp}/resolve", json={"note": "added file"}).status_code == 200
    assert c.get("/v1/history", params={"q": "File not found"}).json()["items"][0]["resolution"] == "added file"


def test_ocr_endpoint():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1500, 160), "black")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((20, 50), "Missing environment variable: DATABASE_URL", fill="white", font=font)
    buf = io.BytesIO(); img.save(buf, "PNG")
    r = c.post("/v1/ocr", files={"file": ("shot.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and "environment variable" in r.json()["text"]
