# -*- coding: utf-8 -*-
"""
content_text.py
The silent kind: Urdu text that scrolls, with music under it and no voice.

WHY THIS EXISTS
  The habit videos are the ones nobody watches. They are the most expensive
  thing this repo makes — eight scenes, eight TTS calls, a minute of runtime —
  and on a page whose only engaging post was a verse, they have returned
  nothing. The scripture side works because it is short, quiet and worth
  screenshotting. This kind takes those three properties and drops everything
  the habit format was spending money on.

  No narration at all. No TTS quota, no voice ladder, no Gemini backoff, and no
  synthetic Urdu accent to be judged on. A viewer scrolling with the sound off
  — which on a reel is most of them — loses nothing, because there was never
  anything to lose.

WHAT IT WRITES
  Three shapes, rotated. They are deliberately the shapes that already travel
  in Urdu feeds rather than anything invented here:

    qoul     one line worth screenshotting, then the thought under it
    mushkil  a problem named in the viewer's own words, then what to do
    yaad     a short reminder in four or five beats, each its own line

  The text is the whole video. There is no hook to write separately, no call to
  action bolted on the end, and no icon: a screenshot of a good line is the
  share, and anything else in the frame is competing with it.

WHAT IT WILL NOT DO
  It does not quote scripture. Not an ayah, not a hadith, not "اللہ فرماتے
  ہیں". That is the scripture kind's job, where the text comes from a published
  API and is checked against it — a religious quotation written by a model is
  the worst thing this channel could publish, and the rule is the same here as
  it is there.
"""
import json
import os
import random

import urdu
from config import DEFAULT_CLAUDE_MODEL, WRITER_EFFORT, LOG_FILE, CHANNEL_NAME
from content import ask, _posted

# One scene. The whole video is a single frame whose text moves, so the
# renderer's per-scene machinery has exactly one thing to render and the scroll
# can be one unbroken movement rather than a cut every four seconds.
TEXT_ROLES = ["card"]

# How long the column takes to travel. Slow enough to read Nastaliq at this
# size, short enough that a viewer who has read it is not left waiting: about
# two and a half seconds a line, floored so a three-line card is not over
# before it registers.
SECONDS_PER_LINE = float(os.environ.get("TEXT_SECONDS_PER_LINE") or 2.6)
MIN_SECONDS = float(os.environ.get("TEXT_MIN_SECONDS") or 14)
MAX_SECONDS = float(os.environ.get("TEXT_MAX_SECONDS") or 34)

SHAPES = {
    "qoul": {
        "lines": (3, 4),
        "brief": (
            "ایک ایسی بات جو لوگ اسکرین شاٹ لے کر رکھ لیں۔ پہلی سطر وہ جملہ ہے، "
            "باقی سطریں اُسے کھولتی ہیں۔ نصیحت نہیں، تسلی۔"),
    },
    "mushkil": {
        "lines": (4, 5),
        "brief": (
            "پہلی دو سطریں وہ مسئلہ جو دیکھنے والا خود محسوس کرتا ہے، اُسی کے "
            "الفاظ میں۔ باقی سطریں ایک چھوٹا سا عملی حل — آج کیا کرنا ہے۔"),
    },
    "yaad": {
        "lines": (4, 5),
        "brief": (
            "ایک مختصر یاد دہانی، ہر سطر اپنی جگہ مکمل۔ کوئی لمبا جملہ نہیں، "
            "ہر سطر آٹھ لفظوں سے کم۔"),
    },
}

SYSTEM = f"""تم "{CHANNEL_NAME}" کے لیے مختصر اردو متن لکھتے ہو۔ یہ ویڈیو خاموش
ہے — کوئی آواز نہیں، صرف لکھائی اسکرین پر اوپر کی طرف چلتی ہے۔ اس لیے جو لکھو
گے، وہی پوری ویڈیو ہے۔

صرف اردو رسم الخط۔ کبھی رومن اردو نہیں، کبھی انگریزی حروف نہیں۔

جو کبھی نہیں لکھنا:
- قرآن یا حدیث کا کوئی حوالہ، کوئی آیت، کوئی روایت — ایک لفظ بھی نہیں۔
  "اللہ فرماتے ہیں"، "حدیث میں ہے" جیسا کوئی جملہ بھی نہیں۔
- کوئی طبی مشورہ، کوئی دوا، کوئی تشخیص۔
- ڈرانا، شرمندہ کرنا، یا کسی کو قصوروار ٹھہرانا۔
- ہیش ٹیگ، ایموجی، یا "فالو کریں" جیسی کوئی بات متن کے اندر۔

لہجہ: نرم، ٹھہرا ہوا، جیسے کوئی قریبی شخص آہستہ بات کر رہا ہو۔

صرف درست JSON دو۔ کوئی markdown، کوئی وضاحت۔"""

PROMPT = """آج کا موضوع: {topic}

اس شکل میں لکھو: {brief}

بالکل {n} سطریں۔ ہر سطر الگ، مکمل، اور {max_words} لفظوں سے کم۔
پہلی سطر سب سے مضبوط ہو — وہی وہ جملہ ہے جس پر اسکرول رکتا ہے۔

ایک سطر میں <em></em> صرف اُس ایک لفظ پر لگاؤ جو سب سے زیادہ وزن رکھتا ہے۔
پوری ویڈیو میں ایک ہی <em> ہو، اس سے زیادہ نہیں۔

JSON:
{{"title":"...","caption":"...","lines":["...","..."]}}

title: یوٹیوب کا عنوان، اردو میں، آٹھ لفظوں سے کم۔
caption: دو یا تین سطریں، آخر میں ہیش ٹیگ۔"""

MAX_WORDS_PER_LINE = int(os.environ.get("TEXT_MAX_WORDS") or 9)


def next_shape() -> str:
    """Which shape today's card takes — rotated on text posts, like the rest."""
    forced = os.environ.get("TEXT_SHAPE")
    if forced:
        if forced not in SHAPES:
            raise ValueError(f"No shape named {forced!r}. Have: "
                             + ", ".join(SHAPES))
        return forced
    posted = len([e for e in _posted()
                  if e.get("results") and e.get("kind") == "text"])
    names = list(SHAPES)
    return names[posted % len(names)]


def duration_for(lines: list[str]) -> float:
    """How long the scroll runs, from how much there is to read."""
    return max(MIN_SECONDS, min(MAX_SECONDS, len(lines) * SECONDS_PER_LINE))


def build_spec(topic: str, pillar: str = "") -> dict:
    """One silent card: a few lines of Urdu and the clock they travel on."""
    shape = next_shape()
    lo, hi = SHAPES[shape]["lines"]
    n = random.randint(lo, hi)
    print(f"  shape: {shape} ({n} lines, silent)")

    raw = ask(SYSTEM, PROMPT.format(topic=topic, brief=SHAPES[shape]["brief"],
                                    n=n, max_words=MAX_WORDS_PER_LINE),
              effort=WRITER_EFFORT)
    spec = json.loads(raw)

    lines = [str(x).strip() for x in (spec.get("lines") or []) if str(x).strip()]
    if not lines:
        raise ValueError("The writer returned no lines")
    # More than asked for is not a failure worth losing the day over; fewer
    # than two is, because one line on its own is a still image with music.
    if len(lines) < 2:
        raise ValueError(f"Only {len(lines)} line(s) — a card needs at least 2")

    hold = duration_for(lines)
    scenes = [{
        "role": "card",
        # The renderer wants a headline; for this kind the lines ARE it, and
        # the template reads them from `lines` rather than from `headline`.
        "headline": lines[0],
        "spoken": "",          # silent: main.py holds it rather than narrating
        "icon": None,
        "profile": "text",
        "lines": lines,
        "hold": hold,
    }]

    out = {
        "title": spec.get("title", ""),
        "caption": spec.get("caption", ""),
        "scenes": scenes,
        "topic": topic,
        "pillar": pillar or shape,
        "shape": shape,
    }
    # Same Roman-Urdu repair every other kind gets. Nothing here is verbatim,
    # so all of it is checked.
    urdu.repair(out, ask)
    print(f"  script: {len(lines)} lines, {hold:.0f}s of scroll")
    return out
