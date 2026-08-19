"""
guard_islamic.py
What the scripture channel is not allowed to say, and what it is not allowed
to have changed.

guard.py protects a wellness channel from making a medical claim. This one has
a different job and a harder one. The risk is not a policy strike; it is
putting words in the mouth of revelation. Two things are checked, and the first
is the one that actually matters:

  1. INTEGRITY. Every scene the writer marked `verbatim` is compared, character
     for character, against the dict islamic_sources.py returned. If the Arabic
     on screen is not the Arabic the API sent, or the translation has drifted
     by one word, the build stops. This is not a style check — it is the only
     thing standing between a bug anywhere upstream and a misquoted ayah
     published under a reference number.

  2. LANGUAGE. The model-written scenes are searched for the four things a
     daily automated channel has no business doing: introducing a quotation it
     invented, issuing a ruling, naming a sect, or promising a reward. The
     patterns are matched against Urdu script, Roman Urdu and English, because
     a writer that slips into Roman Urdu — the bug urdu.py exists for — would
     otherwise slip past the guard at the same time.

Both are fatal by default. Losing a day's video is cheap.
"""
import re
import unicodedata

from guard import UnsafeContent

# --------------------------------------------------------------- 2. language

BANNED = [
    # A quotation the model introduces is a quotation the model invented —
    # everything genuinely quoted in these videos is placed in the frame by
    # content_islamic.py from the API's own fields, never written.
    r"اللہ (تعالیٰ|تعالی)? ?(نے )?(فرمات[ےی] ہیں|فرمایا)",
    r"قرآن (میں|پاک میں|مجید میں) (ہے|آیا|فرمایا)",
    r"(حدیث|روایت) (میں|شریف میں) (ہے|آیا|آتا ہے)",
    r"(نبی|رسول|حضور|آپ) ?(کریم|اکرم)? ?(ﷺ|صلی اللہ علیہ وسلم)? ?نے فرمایا",
    # "in another verse…", "a second hadith says…" — a SECOND quotation, which
    # is one more than this format has a source for. Written narrowly on
    # purpose: the first version of this rule was `ایک (اور )?(آیت|حدیث)` and
    # it refused the channel's own follow line, "روز ایک آیت یا حدیث" — a rule
    # that fails the video for describing the channel is worse than no rule.
    r"(ایک اور|دوسری|اگلی) (آیت|حدیث)",
    r"(آیت|حدیث) میں (ہے|آیا|آتا ہے|فرمایا)",
    r"allah ne farmaya", r"hadees mein hai", r"quran mein hai",
    # Rulings. This is not a fatwa channel and a daily automated one least of
    # all — see the system prompt in content_islamic.py, which says the same
    # thing to the writer.
    r"حرام (ہے|ہیں)", r"حلال (ہے|ہیں)", r"فرض ہے", r"واجب ہے",
    r"بدعت", r"سنت نہیں", r"جائز نہیں", r"ناجائز",
    r"\bharaam? hai\b", r"\bfarz hai\b", r"\bwajib hai\b", r"\bbid'?ah\b",
    # Sects and factions. The fastest way to turn a channel about a verse into
    # a channel about an argument.
    r"شیعہ", r"سنی", r"وہابی", r"بریلوی", r"دیوبندی", r"اہل حدیث",
    r"\bshia\b", r"\bsunni\b", r"\bwahabi\b", r"\bbarelvi\b", r"\bdeobandi\b",
    # Takfir, and judging where a named person ends up.
    r"کافر ہے", r"مشرک ہے", r"منافق ہے", r"جہنم میں جائے گا",
    r"جنت میں جائے گا", r"\bkafir hai\b",
    # Promises of a specific reward or punishment to the viewer. The texts make
    # their own promises; the channel does not add to them.
    r"(جنت|بخشش|مغفرت) (مل|ملے گی|ضرور)", r"ستر (نیکیاں|گنا)",
    r"(ہزار|لاکھ) (نیکیاں|گناہ معاف)",
    r"گناہ معاف ہو جائیں گے",
    # Money attached to worship.
    r"(چندہ|عطیہ|donation)", r"\bdonate\b",
]

NEEDS_CARE = [
    r"ثواب", r"عذاب", r"قیامت", r"موت", r"دعا قبول",
    r"\bsawab\b", r"\bazaab\b",
]

_BANNED_RE = [re.compile(p, re.I) for p in BANNED]
_CARE_RE = [re.compile(p, re.I) for p in NEEDS_CARE]


# --------------------------------------------------------------- 1. integrity

def _norm(text: str) -> str:
    """Compare texts the way a reader would, not the way bytes do.

    NFC, because Arabic diacritics have more than one valid encoding and a
    JSON round-trip can pick the other one — which would fail an integrity
    check on two strings that render identically. Whitespace is collapsed for
    the same reason. Nothing else is touched: a missing letter, a changed
    letter and a dropped word all still fail, which is the entire point.
    """
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def _verbatim_fields(scene: dict, src: dict) -> list[tuple[str, str, str]]:
    """(what, on screen, from the source) for each field that must match."""
    pairs = []
    if scene.get("arabic"):
        pairs.append(("Arabic", scene.get("headline", ""), src.get("arabic", "")))
    if scene["role"] == "tarjuma":
        pairs.append(("Urdu translation", scene.get("spoken", ""),
                      src.get("urdu", "")))
        pairs.append(("reference", scene.get("headline", ""),
                      src.get("citation", "")))
    if scene["role"] == "hadith" and not scene.get("arabic"):
        pairs.append(("Urdu text", scene.get("spoken", ""), src.get("urdu", "")))
    return pairs


def check_integrity(spec: dict) -> None:
    """Every verbatim scene still says exactly what the source said."""
    src = spec.get("source")
    if not src:
        raise UnsafeContent(
            "This spec has no `source` — there is nothing to check the "
            "scripture against, and unverifiable scripture does not ship.")

    checked = 0
    for i, scene in enumerate(spec.get("scenes") or []):
        if not scene.get("verbatim"):
            continue
        for what, screen, origin in _verbatim_fields(scene, src):
            if not _norm(origin):
                raise UnsafeContent(
                    f"scenes[{i}] ({scene['role']}) claims to carry the "
                    f"{what} verbatim, but the source has no such field.")
            if _norm(screen) != _norm(origin):
                raise UnsafeContent(
                    f"scenes[{i}] ({scene['role']}): the {what} on screen is "
                    f"not what {src.get('source')} returned for "
                    f"{src.get('kind')} {src.get('ref')}.\n"
                    f"  on screen: {screen[:90]!r}\n"
                    f"  source   : {origin[:90]!r}")
            checked += 1
    if not checked:
        raise UnsafeContent(
            "No scene in this video is carrying verified scripture. A "
            "scripture video whose scripture is model-written is exactly what "
            "this guard exists to stop.")
    print(f"  integrity: {checked} verbatim field(s) match "
          f"{src['source']} — {src['kind']} {src['ref']}")


# ------------------------------------------------------------------ both, run

def _written_text(spec: dict) -> str:
    """Only what the model wrote. The sources are not policed for their own
    words: a hadith about the Fire says what it says, and running the channel's
    own language rules over revelation would be both useless and backwards."""
    parts = [spec.get("title", ""), spec.get("caption", "")]
    for scene in spec.get("scenes") or []:
        if scene.get("verbatim"):
            continue
        parts += [scene.get("headline", ""), scene.get("spoken", "")]
    return "\n".join(parts)


def check(spec: dict, strict: bool = True) -> list[str]:
    """Integrity first, then language. Same signature as guard.check()."""
    check_integrity(spec)

    text = _written_text(spec)
    hard = sorted({r.pattern for r in _BANNED_RE if r.search(text)})
    soft = sorted({r.pattern for r in _CARE_RE if r.search(text)})

    if hard:
        msg = ("Refusing to build this video — the written parts do something "
               "this channel does not do (quote, rule, take sides, or "
               "promise): " + ", ".join(hard))
        if strict:
            raise UnsafeContent(msg)
        print("  UNSAFE: " + msg)
    if soft:
        print("  guard: heavy but allowed — " + ", ".join(soft))
    return soft


# Goes out with every caption. Not a medical disclaimer — a sourcing line,
# which is the thing a viewer of this channel actually needs to be able to
# check, and the thing that lets someone who knows better correct it.
def disclaimer(spec: dict) -> str:
    src = spec.get("source") or {}
    if src.get("kind") == "quran":
        return (f"آیت: {src.get('citation', '')}\n"
                f"ترجمہ: فتح محمد جالندھری — بحوالہ alquran.cloud\n"
                f"تلاوت: مشاری العفاسی — ترجمہ پڑھا: شمشاد علی خان\n"
                f"تشریح: تفسیر المیسر (مجمع الملك فهد) کی روشنی میں، "
                f"آسان اردو میں\n"
                f"کسی غلطی کی نشاندہی کریں — ہم اسے درست کریں گے۔")
    return (f"حدیث: {src.get('citation', '')}\n"
            f"بحوالہ hadeethenc.com (مجمع الملك سلمان)\n"
            f"کسی غلطی کی نشاندہی کریں — ہم اسے درست کریں گے۔")
