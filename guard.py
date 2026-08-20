"""
guard.py
What the channel is not allowed to say.

A daily Urdu channel in a wellness niche sits inside both platforms' medical
policy. The risk is not that a video gets fewer views — it is that a run of
auto-generated advice nobody read produces one clip that claims a cure, and the
Page takes a strike that costs the whole account. So the guard runs on every
video before a frame is rendered, and a violation is fatal by default: losing
one day's post is cheap, losing the Page is not.

Two separate lists. `BANNED` is language no video may use at all. `NEEDS_CARE`
is language that is fine in a habit video and dangerous in a claim, so it is
allowed but reported, which is how a drift in what the model writes gets
noticed before a viewer notices it.

Note the deliberate difference from the sibling repo's `content_guard.py`,
whose signal words are all English — Urdu-script text scores as irrelevant
there and the gate rejects every real video. These patterns are matched against
Urdu script, Roman Urdu and English, because the writer produces all three.
"""
import re

BANNED = [
    # cure / treatment claims
    r"\bcures?\b", r"\bcured\b", r"\btreats?\b", r"\bheals?\b",
    r"ilaaj", r"ilaj", r"علاج", r"شفا",
    r"\bmarz\b", r"مرض",
    # named conditions — a habits channel has no business naming a diagnosis
    r"cancer", r"کینسر", r"diabetes", r"شوگر", r"ذیابیطس",
    r"depression", r"ڈپریشن", r"blood pressure", r"بلڈ پریشر",
    r"thyroid", r"tumou?r", r"heart attack", r"دل کا دورہ",
    # medication and dosage
    r"\bdose\b", r"\bmg\b", r"\bml\b", r"tablet", r"capsule", r"syrup",
    r"dawa+i?", r"دوا", r"گولی", r"supplement", r"\bpill\b",
    # advice that replaces a doctor
    r"doctor ki zarurat nahi", r"ڈاکٹر کی ضرورت نہیں",
    r"no need (for|to see) a doctor",
    # Body and weight targets. Added when the channel widened to food and
    # exercise. A habit video may say what to DO and when; the moment it names
    # a weight, a calorie count or a body to end up with, it is prescribing —
    # which is both outside what anyone here is qualified to say and squarely
    # inside both platforms' health policy.
    r"calorie", r"کیلوری", r"kcal",
    r"kg", r"کلو وزن", r"وزن کم", r"wazan kam", r"weight loss",
    r"fat ?loss", r"پیٹ کم", r"belly fat", r"موٹاپا",
    r"detox", r"ڈیٹاکس", r"keto", r"protein powder",
    r"(دن|دنوں|ہفتے|مہینے) میں (وزن|نتیجہ|فرق) (کم|ضمانت)",
    # guarantees
    r"guarantee", r"100%", r"یقینی طور پر ٹھیک", r"hamesha ke liye theek",
]

NEEDS_CARE = [
    r"\bfat\b", r"وزن", r"weight", r"\bdiet\b", r"غذا",
    r"\bstress\b", r"\banxiety\b", r"نیند نہ آنا",
]

_BANNED_RE = [re.compile(p, re.I) for p in BANNED]
_CARE_RE = [re.compile(p, re.I) for p in NEEDS_CARE]


class UnsafeContent(Exception):
    pass


def _all_text(spec: dict) -> str:
    parts = [spec.get("title", ""), spec.get("caption", "")]
    for s in spec.get("scenes", []):
        parts += [s.get("headline", ""), s.get("spoken", "")]
    return "\n".join(parts)


def check(spec: dict, strict: bool = True) -> list[str]:
    """Return the list of soft flags; raise UnsafeContent on a hard violation.

    `strict=False` reports instead of raising — for inspecting a draft by hand,
    never for a scheduled run.
    """
    text = _all_text(spec)
    hard = sorted({r.pattern for r in _BANNED_RE if r.search(text)})
    soft = sorted({r.pattern for r in _CARE_RE if r.search(text)})

    if hard:
        msg = ("Refusing to build this video — it makes medical claims a "
               "habits channel must not make: " + ", ".join(hard))
        if strict:
            raise UnsafeContent(msg)
        print("  UNSAFE: " + msg)
    if soft:
        print("  guard: sensitive but allowed — " + ", ".join(soft))
    return soft


DISCLAIMER_UR = (
    "یہ ویڈیو صرف عمومی معلومات کے لیے ہے، طبی مشورہ نہیں۔ "
    "کسی بھی تکلیف میں اپنے ڈاکٹر سے رجوع کریں۔"
)
DISCLAIMER_EN = (
    "General information only — not medical advice. "
    "Consult a qualified doctor about any symptom or condition."
)
