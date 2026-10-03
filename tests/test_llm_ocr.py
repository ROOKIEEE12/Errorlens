import io, json
from pathlib import Path
import pytest
from errorlens.core.analyze import analyze_text
from errorlens.core.llm import build_payload, enrich
from errorlens.core.ocr import ocr_available, ocr_image

S = Path(__file__).parent.parent / "samples"


def test_llm_payload_has_no_raw_log_or_secrets():
    d = analyze_text((S / "missing_env.log").read_text())
    blob = json.dumps(build_payload(d))
    assert "hunter2pass" not in blob and "abcd1234efgh5678" not in blob and "postgresql://admin" not in blob


def test_enrich_validates_and_survives_garbage():
    d = analyze_text((S / "missing_env.log").read_text())
    good = json.dumps({"explanation_en": "Env var missing.", "explanation_hi": "Variable set nahi hai.",
                       "alternative_hypotheses": ["typo in name"], "risk_explanation": "Medium."})
    sent = {}
    def fake(system, user):
        sent["user"] = user
        return "```json\n" + good + "\n```"
    e = enrich(d, transport=fake)
    assert e and e.explanation_hi and "hunter2pass" not in sent["user"]
    assert enrich(d, transport=lambda s, u: "not json at all") is None
    def boom(s, u): raise RuntimeError("network")
    assert enrich(d, transport=boom) is None


@pytest.mark.skipif(not ocr_available(), reason="tesseract not installed")
def test_ocr_roundtrip():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1500, 160), "black")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((20, 50), "Module not found: Can't resolve '@/components/Button'", fill="white", font=font)
    buf = io.BytesIO(); img.save(buf, "PNG")
    text = ocr_image(buf.getvalue())
    assert "Module not found" in text
    assert analyze_text(text).error_type == "module_not_found"
