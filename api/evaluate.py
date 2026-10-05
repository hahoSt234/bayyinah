"""
تقييم محرك التحقق من المضمون على مجموعة اختبار.

التشغيل:
    python evaluate.py

يختبر:
1. كل حديث في القاعدة بنصه، هل يرجع حكمه الصحيح
2. نفس الحديث مكتوب بدون تشكيل ومع كلام قبله وبعده، مثل ما ينقال في مقطع
3. نصوص مو موجودة في القاعدة، هل النظام يمتنع بدل ما يحكم غلط

ويطلع الأرقام اللي نحطها في العرض التقديمي.
"""

import json
import time

from arabic import DIACRITICS
from engine import HadithEngine
from verdict import decide, content_block

# نصوص مو موجودة في القاعدة. الصحيح إن النظام يمتنع (غير محسوم)
NEGATIVES = [
    "الجو اليوم حار جدا في الرياض والناس في الاسواق",
    "اشتريت سيارة جديدة الاسبوع الماضي ولونها ابيض",
    "من صام يوم كذا كتب الله له اجر الف شهيد",
    "من قرأ هذه الرسالة وارسلها لعشرة اشخاص سمع خبرا سارا",
    "الحمد لله رب العالمين والصلاة والسلام على اشرف المرسلين",
    "اجتماع الفريق بكره الساعة تسعة الصبح ان شاء الله",
    "قال احد الحكماء العلم نور والجهل ظلام",
    "من نام بعد العصر فاختلس عقله فلا يلومن الا نفسه",
    "صلوا على النبي واكثروا من الدعاء في هذا اليوم",
    "التقنية الحديثة غيرت حياة الناس في كل مكان",
]

EXPECTED = {"authentic": "supported", "weak": "contradicted", "not_authentic": "contradicted",
            "detailed": "contradicted", "unknown": "undetermined"}

NO_AUDIO = {"signal": None}


def verdict_for(engine, text):
    claims = engine.find_claims(text)
    v, *_ = decide(content_block(claims), NO_AUDIO, None)
    return v, claims


def run():
    e = HadithEngine()
    rows = {"exact": [0, 0], "spoken": [0, 0], "attribution": [0, 0]}
    wrong = []
    t0 = time.time()

    for h in e.db:
        want = EXPECTED[h["grade_class"]]
        for mode, text in (
            ("exact", h["text"]),
            ("spoken", "يقول النبي صلى الله عليه وسلم " + DIACRITICS.sub("", h["text"]) + " فانتبهوا لهذا"),
        ):
            v, claims = verdict_for(e, text)
            ok = v == want
            rows[mode][0] += ok
            rows[mode][1] += 1
            if not ok:
                wrong.append(f"[{mode}] {h['id']} توقعنا {want} وطلع {v}: {h['text'][:40]}")
            # دقة الإسناد: هل الحديث اللي رجع هو نفسه
            if mode == "exact":
                hit = any(c["matched"] and c["hadith"]["id"].replace("-ALT", "") == h["id"].replace("-ALT", "")
                          for c in claims)
                rows["attribution"][0] += hit
                rows["attribution"][1] += 1

    abstain_ok = 0
    for t in NEGATIVES:
        v, _ = verdict_for(e, t)
        abstain_ok += v == "undetermined"
        if v != "undetermined":
            wrong.append(f"[negative] توقعنا امتناع وطلع {v}: {t}")

    ms = (time.time() - t0) * 1000 / (len(e.db) * 2 + len(NEGATIVES))
    pct = lambda a: f"{100 * a[0] / max(a[1], 1):.1f}% ({a[0]}/{a[1]})"
    report = {
        "عدد الأحاديث في القاعدة": len(e.db),
        "دقة الحكم بالنص المطابق": pct(rows["exact"]),
        "دقة الحكم بالنص المنطوق مع كلام قبله وبعده": pct(rows["spoken"]),
        "دقة الإسناد (رجع نفس الحديث)": pct(rows["attribution"]),
        "الامتناع الصحيح عند غياب النص": pct([abstain_ok, len(NEGATIVES)]),
        "متوسط زمن التحقق للنص": f"{ms:.0f} ملي ثانية",
    }
    for k, v in report.items():
        print(f"{k}: {v}")
    if wrong:
        print("\nالحالات اللي ما ضبطت:")
        print("\n".join(wrong))
    with open("data/eval_report.json", "w", encoding="utf-8") as f:
        json.dump({"report": report, "errors": wrong}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()
