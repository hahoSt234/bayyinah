"""
محرك التحقق من المضمون.

يبحث عن الحديث في القاعدة المغلقة فقط، ويرجع الحكم كما هو من المصدر.
ما فيه أي نموذج لغوي يكتب حكم من عنده.
"""

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from arabic import candidate_segments, normalize

# حدود المطابقة. اللي تحت MIN_SCORE يعتبر غير موجود في القاعدة.
EXACT_SCORE = 0.85
MIN_SCORE = 0.55

# كلمات شائعة ما نحسبها في المطابقة
STOP = set("من في على الى عن ان او ثم قال قالوا قلنا الله رسول النبي صلي عليه وسلم ما لا لم و يا هذا هذه ذلك التي الذي كان".split())


def _in_order(query_words, hadith_words):
    """يتأكد إن كلمات الاقتباس جاية بنفس ترتيبها في الحديث."""
    pos = 0
    for w in query_words:
        try:
            pos = hadith_words.index(w, pos) + 1
        except ValueError:
            return False
    return True


class HadithEngine:
    def __init__(self, path="data/hadiths.json"):
        self.db = json.loads(Path(path).read_text(encoding="utf-8"))
        self.by_id = {h["id"]: h for h in self.db}
        self.norm = [normalize(h["text"]) for h in self.db]
        # مقارنة على مستوى الحروف عشان تتحمل اختلاف الإملاء والتشكيل
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.matrix = self.vec.fit_transform(self.norm)

    def _containment(self, seg_words, idx):
        """نسبة كلمات الحديث الموجودة في المقطع وبنفس الترتيب، مفيدة لما الحديث قصير والكلام طويل."""
        hw = [w for w in self.norm[idx].split() if w not in STOP]
        if len(hw) < 3:
            return 0.0
        s = set(seg_words)
        ratio = sum(1 for w in hw if w in s) / len(hw)
        if ratio < 0.9 or not _in_order([w for w in hw if w in s], seg_words):
            return 0.0
        return ratio

    def search(self, text, top_k=3):
        """يرجع أفضل المطابقات لمقطع واحد."""
        n = normalize(text)
        if not n:
            return []
        sims = cosine_similarity(self.vec.transform([n]), self.matrix)[0]
        words = n.split()
        content = [w for w in words if w not in STOP]
        results = []
        for idx in sims.argsort()[::-1][: max(top_k, 8)]:
            cont = self._containment(words, idx)
            score = max(float(sims[idx]), cont if len(self.norm[idx].split()) >= 3 else 0.0)
            # لما المستخدم يقتبس أول الحديث الطويل بس: كم من كلماته موجودة في الحديث بالترتيب
            if len(content) >= 4:
                hw = self.norm[idx].split()
                hset = set(hw)
                qcont = sum(1 for w in content if w in hset) / len(content)
                if qcont >= 0.85 and _in_order(content, hw):
                    score = max(score, 0.6 + 0.24 * qcont)  # تطلع "partial" لأنها جزء من الحديث
            results.append((score, idx))
        results.sort(reverse=True)
        return results[:top_k]

    def find_claims(self, text, max_claims=5):
        """يطلع كل الأحاديث الموجودة في النص، ولو ما لقى شي يرجع النص كادعاء غير موجود."""
        best = {}
        for seg in candidate_segments(text):
            # المقاطع القصيرة جدا (كلمتين) نطلب لها تطابق أعلى عشان ما تطلع نتائج غلط
            limit = MIN_SCORE if len(normalize(seg).split()) >= 3 else 0.8
            hits = self.search(seg, top_k=1)
            if not hits or hits[0][0] < limit:
                continue
            score, idx = hits[0]
            hid = self.db[idx]["id"]
            if hid not in best or score > best[hid][0]:
                best[hid] = (score, seg)

        # إذا الحديث وبديله الصحيح طلعوا مع بعض، ناخذ الأقوى بس من كل زوج
        chosen = sorted(best.items(), key=lambda kv: -kv[1][0])
        claims, used_roots, used_segs = [], set(), []
        for hid, (score, seg) in chosen:
            root = hid.replace("-ALT", "")
            if root in used_roots:
                continue
            words = set(normalize(seg).split())
            # إذا نفس الكلام انطابق مع حديث أقوى، ما نحسبه مرة ثانية
            if any(len(words & u) / max(len(words), 1) > 0.5 for u in used_segs):
                continue
            used_roots.add(root)
            used_segs.append(words)
            claims.append(self._claim(hid, score, seg))
            if len(claims) >= max_claims:
                break

        if not claims:
            claims.append({"quoted_text": text.strip()[:300], "matched": False, "match_type": None, "hadith": None})
        return claims

    def _claim(self, hid, score, seg):
        h = self.by_id[hid]
        alt = h.get("alternative")
        return {
            "quoted_text": seg.strip()[:300],
            "matched": True,
            "match_type": "exact" if score >= EXACT_SCORE else "partial",
            "hadith": {
                "id": h["id"],
                "text": h["text"],
                "grade_raw": h["grade_raw"],
                "grade_class": h["grade_class"],
                "graded_by": h.get("graded_by"),
                "source": h.get("source") or {"book": None, "ref": None},
                "url": h.get("url"),
                "note": h.get("note") or (f"الراوي: {h['narrator']}" if h.get("narrator") else None),
                "alternative": (
                    {
                        "text": alt["text"],
                        "grade_raw": alt.get("grade_raw"),
                        "graded_by": alt.get("graded_by"),
                        "source": alt.get("source"),
                        "url": alt.get("url"),
                    }
                    if alt and alt.get("text")
                    else None
                ),
            },
        }
