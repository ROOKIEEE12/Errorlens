"""FastAPI backend. The CLI, the web UI and the GitHub Action all use the same analyze pipeline.

Run:  uvicorn errorlens.api.main:app --reload
"""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.analyze import analyze_with_log
from ..core.llm import enrich
from ..core.ocr import IMAGE_EXT, OCRUnavailable, ocr_available, ocr_image
from ..core.report import render
from ..storage import sqlite as store

MAX_BYTES = 2 * 1024 * 1024
app = FastAPI(title="ErrorLens API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ERRORLENS_CORS", "http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


async def _read_input(file: UploadFile | None, text: str | None) -> tuple[str, str | None]:
    """Return (log_text, ocr_text_if_image)."""
    if file is not None:
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "File too large (max 2 MB).")
        if Path(file.filename or "").suffix.lower() in IMAGE_EXT:
            try:
                t = ocr_image(data)
            except OCRUnavailable as e:
                raise HTTPException(501, str(e))
            return t, t
        return data.decode("utf-8", errors="replace"), None
    if text and text.strip():
        if len(text.encode()) > MAX_BYTES:
            raise HTTPException(413, "Text too large (max 2 MB).")
        return text, None
    raise HTTPException(400, "Provide `text` or `file`.")


@app.get("/health")
def health():
    return {"status": "ok", "ocr": ocr_available(), "ai": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/v1/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    """Screenshot -> editable text. The UI shows it to the user to fix OCR mistakes before analysis."""
    text, _ = await _read_input(file, None)
    return {"text": text}


@app.post("/v1/analyze")
async def analyze(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    privacy_mode: Literal["local_only", "sanitized_ai"] = Form("local_only"),
    include_diff: bool = Form(True),
    save: bool = Form(True),
    repo_path: Optional[str] = Form(None),
):
    log, ocr_text = await _read_input(file, text)
    repo = None
    if repo_path:
        if os.environ.get("ERRORLENS_ALLOW_REPO_PATH") != "1":
            raise HTTPException(403, "repo_path is disabled. Set ERRORLENS_ALLOW_REPO_PATH=1 on a local, trusted server.")
        repo = repo_path
    d, redacted_log = analyze_with_log(log, repo=repo, with_diff=include_diff)

    recurrence = None
    if save:
        row = store.record(d)
        recurrence = {"count": row["count"], "first_seen": row["first_seen"], "last_seen": row["last_seen"], "resolution": row["resolution"]}
    d.related = store.related(d.error_type, d.fingerprint)

    ai_status = "off"
    if privacy_mode == "sanitized_ai":
        d.ai = enrich(d)
        ai_status = "ok" if d.ai else "unavailable (no ANTHROPIC_API_KEY or the model call failed)"

    return {
        "analysis_id": "an_" + uuid.uuid4().hex[:10],
        "diagnosis": d.model_dump(),
        "redacted_log": redacted_log,       # what the user can safely copy; raw input is never stored
        "ocr_text": ocr_text,
        "recurrence": recurrence,
        "ai_status": ai_status,
        "privacy": {"mode": privacy_mode, "raw_log_stored": False},
    }


class SafeReportIn(BaseModel):
    text: str
    format: Literal["markdown", "json", "text", "github"] = "markdown"
    repo_path: Optional[str] = None


@app.post("/v1/reports/safe")
def safe_report(body: SafeReportIn):
    """Generate a share-safe report (built from the redacted diagnosis only)."""
    d, _ = analyze_with_log(body.text, with_diff=False)
    return {"format": body.format, "report": render(d, body.format), "fingerprint": d.fingerprint}


@app.get("/v1/history")
def history(q: Optional[str] = None, limit: int = 30):
    rows = store.search(q, limit) if q else store.recent(limit)
    return {"items": [dict(r) for r in rows]}


class ResolveIn(BaseModel):
    note: str


@app.post("/v1/history/{fingerprint}/resolve")
def resolve(fingerprint: str, body: ResolveIn):
    if not store.resolve(fingerprint, body.note):
        raise HTTPException(404, "Unknown fingerprint")
    return {"ok": True}
