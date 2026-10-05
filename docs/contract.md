# ربط واجهة بيّنة بالنظام

هنوف، هذا الملف فيه كل اللي تحتاجينه عشان تربطين الواجهة بالنظام.

الفكرة ببساطة: الواجهة ما تحلل ولا تحكم بشي. ترسل المدخل للنظام، والنظام يرجع النتيجة كاملة جاهزة، حتى العناوين والنصوص العربية، والواجهة تعرضها مثل ما هي.

---

## الروابط

- `GET /health` تناديها أول ما يفتح التطبيق عشان يصحى الخادم
- `POST /analyze` ترسلين له المدخل ويرجع لك التقرير

الرابط الأساسي ارسله لك يوم الأحد. لين ذاك الوقت اشتغلي على الأمثلة اللي في مجلد `mock`.

---

## وش ترسلين

`multipart/form-data` فيها:

- `input_type`: يا `audio` يا `video` يا `url` يا `text`
- `file`: الملف إذا صوت أو فيديو (حده 50 ميقا)
- `url`: إذا رابط
- `text`: إذا نص
- `context`: اختياري، إذا كتب المستخدم وش انقال في المقطع

```js
const fd = new FormData();
fd.append("input_type", S.tab);
if (S.file) fd.append("file", S.file);
if (S.tab === "url") fd.append("url", S.url);
if (S.tab === "text") fd.append("text", S.text);
if (S.ctx) fd.append("context", S.ctx);

const res = await fetch(API_BASE + "/analyze", { method: "POST", body: fd });
const data = await res.json();
if (!res.ok) throw Error(data.error.message);
S.rep = data;
```

التحليل ياخذ من 5 ثواني لدقيقة حسب طول المقطع، فخلي شريط التقدم مثل ما هو.

---

## وش يرجع لك

افتحي الأمثلة الثلاث في مجلد `mock` وبتفهمين الشكل على طول. أهم الحقول:

**النتيجة**
- `verdict`: يا `supported` يا `contradicted` يا `undetermined`
- `verdict_title` و `verdict_summary`: العنوان والسطر اللي تحته، جاهزين للعرض
- `disclaimer`: التنبيه اللي تحت التقرير

**الأصالة التقنية** `evidence.authenticity`
- `signal`: `likely_human` أخضر، `inconclusive` برتقالي، `likely_synthetic` أحمر، و null إذا ما انفحص
- `label`: النص اللي يطلع
- `waveform`: أرقام لرسم الموجة بس

**مطابقة صوت المتحدث** `evidence.speaker_match`
- `status` و `label`

**المطابقة مع الأصل** `evidence.original_match`
- `status`: `found` أو `not_found` أو `not_applicable`
- `source`: بيانات الدرس الأصلي
- `before` و `after`: وش قبل المقطع ووش بعده

**التحقق من المضمون** `evidence.content.claims`

قائمة، لأن المقطع ممكن يكون فيه أكثر من حديث. لكل حديث:
- `quoted_text`: النص مثل ما انقال في المقطع
- `hadith.grade_raw`: الحكم بلفظه من المصدر، مثل «ليس هو بثابت». اعرضيه مثل ما هو
- `hadith.grade_class`: للون بس
- `hadith.graded_by`: مين حكم عليه
- `hadith.source`: الكتاب والرقم
- `hadith.note`: إذا فيه تفصيل
- `hadith.alternative`: البديل الصحيح، وإذا null لا تعرضين الصندوق

---

## الأخطاء

إذا صار خطأ يرجع لك كذا:

```json
{ "error": { "code": "file_too_large", "message": "حجم الملف يتجاوز 50 ميقابايت." } }
```

اعرضي `message` في مربع الخطأ اللي عندك.

---

## حقولك الحالية وش يقابلها

| عندك الحين | صار |
|---|---|
| `ai.verdict` | `verdict` |
| `V[...].t` و `V[...].s` | `verdict_title` و `verdict_summary` |
| `ai.claim` | `claims[i].quoted_text` |
| `ai.reason` | `claims[i].hadith.grade_raw` و `graded_by` |
| `ai.refs` | `claims[i].hadith.source` و `url` |
| `ai.orig` | `evidence.original_match` |
| `ai.before` و `ai.after` | `original_match.before` و `after` |
| `ai.caveat` | `disclaimer` |
| `tech.na` | `authenticity.status == "not_applicable"` |
| `tech.level` و `tech.verdict` | `authenticity.signal` و `label` |
| `tech.peaks` | `authenticity.waveform` |
| `tech.dur` | `transcript.duration_sec` |
| `tech.sil` و `tech.cv` | احذفيهم، ما نعرض أرقام خام |

---

## المطلوب منك

احذفي:
- دالة `analyze()`
- دالة `ask()` و `window.claude` والمثال الثابت «إنما الأعمال بالنيات»

ضيفي:
- مين حكم على الحديث
- صندوق البديل الصحيح
- سطر لمطابقة صوت المتحدث
- إذا فيه أكثر من حديث يطلعون كلهم

وعشان تجربين الحين:

```js
const MOCK = true; // يوم الأحد نخليها false
const url = MOCK ? "mock/" + pick + ".json" : API_BASE + "/analyze";
```

و `pick` يا `supported` يا `contradicted` يا `undetermined`.

---

الأحاديث اللي في الأمثلة من ملف هيفاء، وهي للتجربة لين تخلص مراجعتها.

نورة
