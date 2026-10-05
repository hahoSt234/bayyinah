"""
بيّنة: الواجهة البرمجية.

التشغيل على الجهاز:
    uvicorn app:app --reload --port 7860
"""

import os
import tempfile
import time
import uuid

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from audio import AudioError, authenticity, load_audio, transcribe
from engine import HadithEngine
from verdict import TITLES, content_block, decide

MAX_MB = 50

app = FastAPI(title="Bayyinah API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = HadithEngine()


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.get("/health")
def health():
    return {"status": "ok", "hadiths": len(engine.db)}


NOT_APPLICABLE = {
    "speaker_match": {"status": "not_applicable", "label": "المدخل نص"},
    "original_match": {"status": "not_applicable", "label": "المدخل نص", "source": None, "before": None, "after": None},
    "authenticity": {"status": "not_applicable", "signal": None, "label": "المدخل نص، فلم يُجرَ الفحص التقني", "waveform": None},
}


@app.post("/analyze")
async def analyze(
    input_type: str = Form(...),
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    text: str | None = Form(None),
    context: str | None = Form(None),
):
    t0 = time.time()
    input_type = (input_type or "").strip()
    if input_type not in ("audio", "video", "url", "text"):
        return error(400, "unsupported_format", "نوع المدخل غير مدعوم.")

    duration = None
    evidence = {k: dict(v) for k, v in NOT_APPLICABLE.items()}

    # ---------- النص ----------
    if input_type == "text":
        transcript = (text or "").strip()
        if len(transcript) < 8:
            return error(422, "no_speech", "اكتب نصاً لا يقل عن ٨ أحرف.")

    # ---------- الرابط: ما نحمل المقطع، نعتمد على النص اللي كتبه المستخدم ----------
    elif input_type == "url":
        transcript = (context or "").strip()
        if len(transcript) < 8:
            return error(422, "no_speech", "التحليل من الرابط مباشرة غير متاح حالياً، أضف ما قيل في المقطع.")
        evidence["authenticity"]["label"] = "لم يُحمَّل المقطع من الرابط، فلم يُجرَ الفحص التقني"

    # ---------- الصوت والفيديو ----------
    else:
        if file is None:
            return error(422, "unsupported_format", "اختر ملفاً أولاً.")
        data = await file.read()
        if len(data) > MAX_MB * 1024 * 1024:
            return error(413, "file_too_large", f"حجم الملف يتجاوز {MAX_MB} ميقابايت.")
        suffix = os.path.splitext(file.filename or "")[1] or ".bin"
        # على ويندوز ما ينفع نفتح الملف المؤقت وهو مفتوح، فنقفله ونحذفه بأنفسنا
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            wav, duration = load_audio(tmp.name)
        except AudioError as e:
            return error(422, e.code, e.message)
        finally:
            tmp.close()
            os.remove(tmp.name)
        # الملف ينحذف هنا، وما نحتفظ بأي مقطع بعد التحليل

        evidence["authenticity"] = authenticity(wav, duration)
        evidence["speaker_match"] = {"status": "no_reference",
                                     "label": "لا تتوفر عينة مرجعية لصوت المتحدث المنسوب إليه"}
        evidence["original_match"] = {"status": "not_found",
                                      "label": "أرشيف الدروس الأصلية قيد البناء، فلم تُجرَ المطابقة",
                                      "source": None, "before": None, "after": None}
        try:
            transcript = transcribe(wav)
        except AudioError as e:
            if context and len(context.strip()) >= 8:
                transcript = context.strip()
            else:
                return error(422, e.code, e.message)

    # ---------- التحقق من المضمون ----------
    claims = engine.find_claims(transcript)
    evidence["content"] = content_block(claims)
    verdict, summary, abstain, disclaimer = decide(evidence["content"], evidence["authenticity"], duration)

    return {
        "request_id": uuid.uuid4().hex[:12],
        "input_type": input_type,
        "processing_ms": int((time.time() - t0) * 1000),
        "verdict": verdict,
        "verdict_title": TITLES[verdict],
        "verdict_summary": summary,
        "abstain_reason": abstain,
        "transcript": {"available": True, "text": transcript, "duration_sec": round(duration, 1) if duration else None},
        "evidence": evidence,
        "disclaimer": disclaimer,
    }
