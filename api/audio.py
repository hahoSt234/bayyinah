"""
معالجة الصوت: قراءة الملف، والتفريغ النصي، وفحص الأصالة.

كل النماذج تنحمل أول مرة تنطلب بس، عشان الخادم يقوم بسرعة.
"""

import os
import subprocess

import numpy as np

SAMPLE_RATE = 16000
MIN_SECONDS = 2.0        # أقصر من كذا ما نحلله
SHORT_SECONDS = 6.0      # أقصر من كذا نعتبر فحص الأصالة غير كافي

WHISPER_SIZE = os.getenv("WHISPER_SIZE", "small")
DEEPFAKE_MODEL = os.getenv("DEEPFAKE_MODEL", "").strip()  # يتحدد يوم الاثنين بعد التجربة

_whisper = None
_detector = None


class AudioError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def load_audio(path):
    """يحول أي صوت أو فيديو إلى موجة 16 كيلوهرتز قناة وحدة."""
    cmd = ["ffmpeg", "-nostdin", "-i", path, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-f", "f32le", "-loglevel", "error", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, timeout=120).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise AudioError("unsupported_format", "تعذّر قراءة الصوت من الملف. جرّب صيغة MP3 أو WAV أو MP4.")
    wav = np.frombuffer(out, dtype=np.float32)
    duration = len(wav) / SAMPLE_RATE
    if duration < MIN_SECONDS:
        raise AudioError("audio_too_short", "المقطع قصير جداً للتحليل.")
    if np.abs(wav).max() < 1e-3:
        raise AudioError("no_speech", "لم يُعثر على كلام في المقطع.")
    return wav, duration


def waveform(wav, bars=32):
    """أرقام بين 0 و1 لرسم الموجة في الواجهة فقط."""
    chunks = np.array_split(np.abs(wav), bars)
    peaks = np.array([c.max() if len(c) else 0 for c in chunks])
    top = peaks.max() or 1.0
    return [round(float(p / top), 2) for p in peaks]


def transcribe(wav):
    global _whisper
    try:
        if _whisper is None:
            from faster_whisper import WhisperModel
            _whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
        segments, _ = _whisper.transcribe(wav, language="ar", beam_size=1, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception:
        raise AudioError("transcription_failed", "تعذّر التفريغ النصي للمقطع.")
    if not text:
        raise AudioError("no_speech", "لم يُعثر على كلام في المقطع.")
    return text


FAKE_WORDS = ("fake", "spoof", "synthetic", "deepfake", "generated")


def authenticity(wav, duration):
    """فحص هل الصوت مولَّد. النتيجة مستوى وصفي، وما نرجع أي رقم خام."""
    base = {"status": "checked", "waveform": waveform(wav)}

    if not DEEPFAKE_MODEL:
        return {**base, "status": "not_applicable", "signal": None,
                "label": "فحص التزييف قيد التفعيل في هذه النسخة"}

    if duration < SHORT_SECONDS:
        return {**base, "signal": "inconclusive", "label": "القرائن غير كافية لأن المقطع قصير جداً"}

    global _detector
    try:
        if _detector is None:
            from transformers import pipeline
            _detector = pipeline("audio-classification", model=DEEPFAKE_MODEL)
        clip = wav[: SAMPLE_RATE * 30]
        preds = _detector({"raw": clip, "sampling_rate": SAMPLE_RATE}, top_k=None)
        p_fake = sum(p["score"] for p in preds if any(w in p["label"].lower() for w in FAKE_WORDS))
    except Exception:
        return {**base, "status": "failed", "signal": None, "label": "تعذّر إجراء فحص الأصالة"}

    # حدود محافظة: ما نقول مولَّد أو بشري إلا بثقة عالية، والباقي غير حاسم
    if p_fake >= 0.85:
        return {**base, "signal": "likely_synthetic", "label": "قرينة قوية على أن الصوت مولَّد"}
    if p_fake <= 0.15:
        return {**base, "signal": "likely_human", "label": "لا تظهر قرائن على توليد الصوت"}
    return {**base, "signal": "inconclusive", "label": "القرائن غير كافية للحكم على أصالة الصوت"}
