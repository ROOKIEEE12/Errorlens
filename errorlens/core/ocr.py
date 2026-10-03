"""Screenshot OCR (optional: needs Pillow, pytesseract and the tesseract binary)."""
from __future__ import annotations
import io
import shutil

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


class OCRUnavailable(RuntimeError):
    pass


def ocr_available() -> bool:
    try:
        import PIL, pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def ocr_image(data: bytes) -> str:
    """Return cleaned text. The UI shows this to the user as EDITABLE text because OCR makes mistakes."""
    if not ocr_available():
        raise OCRUnavailable("OCR needs: pip install 'errorlens[ocr]' and the tesseract binary (apt install tesseract-ocr).")
    import pytesseract
    from PIL import Image, ImageOps, ImageStat
    img = Image.open(io.BytesIO(data)).convert("L")
    if img.width < 1400:                                   # upscale small screenshots; helps tesseract a lot
        scale = 1400 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    if ImageStat.Stat(img).mean[0] < 110:    # dark terminal -> invert
        img = ImageOps.invert(img)
    text = pytesseract.image_to_string(img, config="--psm 6")
    return "\n".join(l.rstrip() for l in text.splitlines() if l.strip())
