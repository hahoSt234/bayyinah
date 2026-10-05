"""
قواعد الحكم النهائي ودمج القرائن.

المبدأ: ما نقول "مؤيد" أو "مخالف" إلا بقرينة واضحة من المصدر، وغير كذا نمتنع ونحيل للمختص.
"""

TITLES = {
    "supported": "مؤيَّد بالمصدر",
    "contradicted": "مخالف للمصدر",
    "undetermined": "غير محسوم",
}

DISCLAIMER = "التقرير قرائن مساعدة وليس حكماً قطعياً، والمرجع في الحكم أهل العلم."
NOT_FOUND_NOTE = "عدم العثور على النص في قاعدتنا لا يعني أنه موضوع. "

BAD = {"not_authentic", "weak", "detailed"}


def decide(content, auth, duration):
    """يرجع (verdict, summary, abstain_reason, disclaimer)."""
    claims = content["claims"]
    matched = [c for c in claims if c["matched"]]
    classes = [c["hadith"]["grade_class"] for c in matched]
    synthetic = auth.get("signal") == "likely_synthetic"

    # 1. صوت مولَّد بقرينة قوية: مخالف مهما كان المضمون
    if synthetic:
        extra = "، والحديث الوارد لا يثبت" if any(c in BAD for c in classes) else ""
        return ("contradicted", f"مع المقطع قرائن قوية على توليد الصوت{extra}", None, DISCLAIMER)

    # 2. في المقطع حديث لا يثبت
    if any(c in BAD for c in classes):
        n = sum(1 for c in classes if c in BAD)
        what = "الحديث الوارد في المقطع لا يثبت" if n == 1 else f"في المقطع {n} أحاديث لا تثبت"
        if "detailed" in classes and n == 1:
            what = "الحديث الوارد في المقطع لا يثبت بهذا اللفظ أو النسبة، وفي الحكم تفصيل"
        return ("contradicted", what, None, DISCLAIMER)

    # 3. حكم غير مصنف في القاعدة: نمتنع
    if any(c == "unknown" for c in classes):
        return ("undetermined", "حكم الحديث في القاعدة يحتاج مراجعة المختص", "unknown_grade", DISCLAIMER)

    # 4. ما لقينا شي في القاعدة: نمتنع
    if not matched:
        reason = "no_match"
        if duration is not None and duration < 6:
            reason = "short_audio_and_no_match"
        return ("undetermined", "لا تكفي القرائن للحكم، ويُحال المقطع إلى المختص", reason,
                NOT_FOUND_NOTE + DISCLAIMER)

    # 5. كل الأحاديث صحيحة، والصوت ما فيه قرينة توليد
    if auth.get("signal") == "inconclusive":
        return ("supported", "المضمون ثابت في المصادر المعتمدة، وفحص أصالة الصوت غير حاسم", None, DISCLAIMER)
    return ("supported", "المضمون ثابت في المصادر المعتمدة", None, DISCLAIMER)


def content_block(claims):
    matched = [c for c in claims if c["matched"]]
    if not matched:
        return {"status": "not_found", "label": "لم يُعثر على هذا النص في المصادر المتاحة", "claims": claims}
    bad = [c for c in matched if c["hadith"]["grade_class"] in BAD]
    label = "الحديث الوارد لا يثبت" if bad else "الحديث ثابت"
    if len(matched) > 1:
        label = f"وُجد {len(matched)} أحاديث في المصادر"
    return {"status": "verified", "label": label, "claims": claims}
