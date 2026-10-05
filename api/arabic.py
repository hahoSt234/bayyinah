"""تطبيع النص العربي قبل البحث."""

import re

DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
NON_ARABIC = re.compile(r"[^ء-ي0-9\s]")
SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """يوحد الكتابة: يحذف التشكيل والتطويل وعلامات الترقيم، ويوحد الهمزات والياء والتاء المربوطة."""
    if not text:
        return ""
    t = DIACRITICS.sub("", text)
    t = t.replace(TATWEEL, "")
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي")
    t = t.replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = NON_ARABIC.sub(" ", t)
    return SPACES.sub(" ", t).strip()


SENTENCE_SPLIT = re.compile(r"[.!?؟،,;؛:\n«»\"]+")
QUOTE_MARKERS = re.compile(
    r"(قال رسول الله|قال النبي|يقول النبي|يقول رسول الله|عن النبي|صلى الله عليه وسلم|ﷺ)"
)


def candidate_segments(text: str, window: int = 18, step: int = 6):
    """يقطع النص الطويل الى مقاطع متداخلة، لأن الحديث قد يكون جزءا من كلام اطول."""
    pieces = [p.strip() for p in SENTENCE_SPLIT.split(QUOTE_MARKERS.sub(".", text)) if p.strip()]
    segments = list(pieces)
    words = normalize(text).split()
    if len(words) > window:
        for i in range(0, len(words) - window + 1, step):
            segments.append(" ".join(words[i : i + window]))
    segments.append(text)
    seen, out = set(), []
    for s in segments:
        n = normalize(s)
        if len(n.split()) >= 2 and n not in seen:
            seen.add(n)
            out.append(s)
    return out
