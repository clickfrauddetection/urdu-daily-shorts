# -*- coding: utf-8 -*-
"""
guard_ibrat.py
What the story kind is not allowed to do.

guard.py stops a wellness channel making a medical claim. guard_islamic.py
stops a scripture channel putting words in the mouth of revelation, and checks
that the verse on screen is still the verse the API sent. This one runs
guard_islamic in full — the ibrat video ends on a real verse and every one of
those reasons applies to it unchanged — and then adds the two failures that
belong to this format and to no other:

  1. TELLING A MADE-UP STORY AS A TRUE ONE.
     The story is written by a model. That is fine, and it is what the format
     is: a picture of a situation, the way a teacher draws one. It stops being
     fine the moment the video says it happened. "ایک سچا واقعہ", "یہ واقعہ
     ہے" — a viewer who takes that at face value has been told a fabricated
     event by a religious channel, under a verse, which is the one thing a
     channel like this cannot come back from.

  2. PUTTING A PROPHET OR A COMPANION IN IT.
     A story about the Prophet (ﷺ) or a Sahabi is a narration, and a narration
     written by a model is an invented hadith with the isnad filed off. There
     is no version of this the format needs: the whole point is an ordinary
     person in an ordinary afternoon. So the names and the honorifics are
     refused in the WRITTEN scenes outright — the verse itself is verbatim and
     is never searched, so a translation that mentions a prophet is untouched.

Both are fatal, like everything else in this repo's guards. Losing one day's
video is cheap.
"""
import re

import config
import guard_islamic
from guard import UnsafeContent
from guard_islamic import _written_text

BANNED = [
    # ── 1. the story presented as an event ──────────────────────────────────
    # Narrow on purpose. The bare word واقعہ is not banned: "اس واقعے میں" is
    # a normal way to refer back to a scene you have just shown. What is
    # refused is the CLAIM — that it is true, that it happened, that it is
    # being reported rather than drawn.
    r"(سچا|سچی|حقیقی|اصل|ایک) واقعہ",
    r"یہ واقعہ (ہے|پیش آیا|ہوا)",
    r"واقعی (ہوا|پیش آیا)",
    r"ایسا (ہوا تھا|ہی ہوا)",
    r"(حقیقت میں|اصل میں) (ہوا|پیش آیا)",
    r"\b(sacha|haqeeqi|asal) waqia\b", r"\btrue story\b",
    r"روایت ہے کہ", r"بیان کیا جاتا ہے کہ", r"کہتے ہیں کہ ایک",

    # ── 2. a prophet, a companion or a saint as a character ─────────────────
    # The honorifics are the reliable signal — a model writing this kind of
    # story reaches for them before it reaches for a name.
    r"ﷺ", r"صلی اللہ علیہ وسلم", r"علیہ السلام", r"علیہا السلام",
    r"رضی اللہ (عنہ|عنہا|عنہم)", r"رحمۃ اللہ علیہ",
    r"حضرت", r"صحابی", r"صحابہ", r"تابعی", r"ولی اللہ",
    r"(نبی|رسول|پیغمبر) (کریم|اکرم|پاک)?",
    r"\bhazrat\b", r"\bsahabi\b", r"\bnabi\b", r"\brasool\b",
]

_BANNED_RE = [re.compile(p, re.I) for p in BANNED]


def check(spec: dict, strict: bool = True) -> list[str]:
    """guard_islamic's checks, then this format's own. Same signature as
    guard.check()."""
    # Integrity first, and it is the same integrity: the closing scene is
    # marked verbatim and carries the translation and the reference, so
    # guard_islamic._verbatim_fields already knows how to check it.
    soft = guard_islamic.check(spec, strict=strict)

    # Only what the model wrote. The verse is not policed for its own words —
    # running a channel's language rules over revelation would be both useless
    # and backwards, and this list would trip over the first translation that
    # mentions a prophet.
    text = _written_text(spec)
    hard = sorted({r.pattern for r in _BANNED_RE if r.search(text)})
    if hard:
        msg = ("Refusing to build this video — the story does something an "
               "invented story must not do (claim it happened, or put a "
               "prophet or a companion in it): " + ", ".join(hard))
        if strict:
            raise UnsafeContent(msg)
        print("  UNSAFE: " + msg)
    return soft


def disclaimer(spec: dict) -> str:
    """Goes out with every caption.

    Two things, and the first one is not decoration. The story is a made-up
    example, and a viewer who has just watched a religious channel tell one
    deserves to be told so in the caption rather than left to assume. The
    second is the sourcing line for the verse, which is what lets somebody who
    knows better tell us we got it wrong.
    """
    src = spec.get("source") or {}
    made_up = ("یہ کہانی صرف ایک مثال ہے — کوئی پیش آیا ہوا واقعہ نہیں۔")
    if src.get("kind") == "quran":
        return (f"{made_up}\n\n"
                f"آیت: {src.get('citation', '')}\n"
                f"ترجمہ: فتح محمد جالندھری — بحوالہ alquran.cloud\n"
                f"ترجمہ پڑھا: {config.QURAN_UR_RECITER_NAME}\n"
                f"کسی غلطی کی نشاندہی کریں — ہم اسے درست کریں گے۔")
    return (f"{made_up}\n\n"
            f"حدیث: {src.get('citation', '')}\n"
            f"بحوالہ hadeethenc.com (مجمع الملك سلمان)\n"
            f"کسی غلطی کی نشاندہی کریں — ہم اسے درست کریں گے۔")
