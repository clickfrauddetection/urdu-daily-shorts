# -*- coding: utf-8 -*-
"""
templates/scene_text.py
The silent card: one frame, and the text walks up it.

WHY IT IS ONE SCENE AND NOT SEVERAL
  Every other kind here cuts between scenes because a narrator is speaking and
  the cut lands on a sentence. There is no narrator in this one. A cut with
  nothing driving it reads as a glitch, and worse, it takes the line the reader
  was halfway through off the screen. So the whole video is a single frame with
  a single unbroken movement, and the reader sets their own pace inside it.

WHY IT SCROLLS RATHER THAN FADES
  A fade between lines shows one line at a time, which means a viewer who
  arrives late has missed the ones before it. A column that travels keeps the
  earlier lines on screen while the later ones arrive: someone who starts
  watching four seconds in still gets the argument. It is also the shape Urdu
  text posts already take in these feeds, which is not a small thing on a page
  with six followers — looking like what people already stop for is most of the
  battle.

THE FIRST LINE IS PINNED
  The column starts with its first line already in the upper third rather than
  below the fold. Frame one is the only frame most viewers ever see, and a
  frame whose text has not arrived yet is a frame that says nothing.
"""
import os

from config import (
    WIDTH, HEIGHT, PALETTE, SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT,
    CHANNEL_NAME_UR,
)
from templates.scene import _font_url

# Measure-and-shrink rules, same contract as the other templates. One entry:
# the column. Eight lines is where a card stops being a card, and by then the
# type is small enough that the shrink is the wrong answer anyway — the writer
# is capped well below this.
# How far a card that already fits still travels. Enough that the frame is
# never static — a still frame with music reads as a broken video — and far
# short of moving a line out of the safe area.
DRIFT = int(os.environ.get("TEXT_DRIFT_PX") or 70)

FITS = [(".col", 8, 44)]


def fits_for(scene: dict) -> list[tuple[str, int, int]]:
    return FITS


def _words(line: str) -> list[str]:
    """A line split into words, with any <em>word</em> kept whole.

    The writer is told to mark exactly one word, so an <em> never spans a
    space in practice — but splitting on whitespace alone would still tear the
    tags apart the day it does, and a half-open tag takes the rest of the card
    with it.
    """
    out, buf, depth = [], [], 0
    for tok in line.split():
        depth += tok.count("<em>") - tok.count("</em>")
        buf.append(tok)
        if depth <= 0:
            out.append(" ".join(buf))
            buf, depth = [], 0
    if buf:
        out.append(" ".join(buf))
    return out


def _lit_html(lines: list[str], start: float, span: float) -> str:
    """The lines as word spans, timed to be read across `span` seconds.

    The pace comes from the card's own clock rather than a words-per-minute
    constant: however many words there are, the last one lights just before
    the card ends. A long card is read slowly and a short one briskly, which
    is what a person does anyway.
    """
    per_line = [_words(ln) for ln in lines]
    total = sum(len(w) for w in per_line) or 1
    step = span / total

    html, i = [], 0
    for words in per_line:
        spans = []
        for w in words:
            spans.append(
                f'<span class="w" style="animation-delay:'
                f'{start + i * step:.3f}s">{w}</span>')
            i += 1
        html.append('<div class="ln">' + " ".join(spans) + "</div>")
    return "".join(html)


def render_scene(scene: dict, duration: float, lead: float,
                 index: int, total: int) -> str:
    """One silent card. `scene` needs: lines. duration drives the scroll."""
    p = PALETTE
    lines = scene.get("lines") or [scene.get("headline", "")]

    # How far the column travels. It starts with the first line pinned near the
    # top third and ends with the last line just clear of the safe area, so the
    # distance is the column's own height minus the window it moves through —
    # computed in CSS rather than here, because only the browser knows how tall
    # Nastaliq set at this size actually is.
    #
    # The whole travel happens over the scene, minus a beat at each end: a
    # column already moving on frame one looks like it started without you, and
    # one still moving at the cut looks cut off.
    # Line one is on screen almost immediately. The first version held it back
    # 0.9s behind a 0.7s fade, and a probe at t=1s found no ink at all — on a
    # silent card the first second IS the video, and a blank one is a scroll
    # past. The rest follow closely enough to read as one block arriving.
    settle = 0.25
    travel = max(duration - settle - 0.6, 1.0)

    # The sweep finishes a beat before the card does, so the last word is lit
    # and readable rather than lighting as the video cuts.
    body = _lit_html(lines, settle, max(travel - 0.8, 1.0))

    return f"""<!doctype html><meta charset="utf-8">
<style>
@font-face {{ font-family:'NastaliqUrdu'; font-weight:400 700;
  src:url('{_font_url("NotoNastaliqUrdu-Bold.ttf")}') format('truetype'); }}
@font-face {{ font-family:'SansArabic'; font-weight:100 900;
  src:url('{_font_url("NotoSansArabic-SemiBold.ttf")}') format('truetype'); }}

* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ background:transparent; width:{WIDTH}px; height:{HEIGHT}px;
  overflow:hidden; }}
body {{ direction:rtl; color:{p["ink"]};
  -webkit-font-smoothing:antialiased; }}

/* Darker than the other templates' scrim and flat rather than graded. There is
   no headline here that the eye should land on — every line matters equally —
   so an even wash reads better than a spotlight, and the type needs the
   contrast for longer because it is on screen for longer. */
.scrim {{ position:absolute; inset:0;
  background:linear-gradient(180deg,
    rgba(6,10,18,.55) 0%, rgba(6,10,18,.66) 45%, rgba(6,10,18,.72) 100%); }}

.brand {{ position:absolute; top:{SAFE_TOP - 74}px; right:{SAFE_RIGHT}px;
  font-family:'NastaliqUrdu','SansArabic',serif; direction:rtl;
  font-size:34px; line-height:1.9; color:{p["ink"]}; opacity:.72;
  text-shadow:0 2px 14px rgba(0,0,0,.55); }}

/* The window the column travels through. Kept inside the safe area on every
   side: the bottom third of a reel is the caption bar and the right edge is
   the like/share column, and text that scrolls under either is text nobody
   reads. */
.win {{ position:absolute; left:{SAFE_LEFT}px; right:{SAFE_RIGHT}px;
  top:{SAFE_TOP}px; bottom:{SAFE_BOTTOM}px; overflow:hidden;
  /* Centred, so a three-line card sits in the middle of the frame instead of
     clinging to the top. A card that overflows starts at the top instead and
     the scroll below carries the rest up. */
  display:flex; align-items:center; }}

.col {{ width:100%;
  display:flex; flex-direction:column; gap:38px;
  animation:walk {travel:.2f}s linear {settle:.2f}s forwards; }}

@keyframes walk {{
  from {{ transform:translateY(0); }}
  /* One expression covers both cards. WINDOW - 100% is the column's overflow:
     negative when the text is taller than the window, positive when it fits.
     min() therefore scrolls a long card by exactly its overflow, and gives a
     short one the {DRIFT}px drift instead — enough to read as movement in a
     feed without carrying anything off the frame.
     The first version used calc(-100% + WINDOW), which is the same quantity
     with the sign the wrong way round: on a five-line card it came out
     POSITIVE and walked the text downwards. Measured, not spotted. */
  to   {{ transform:translateY(min(-{DRIFT}px,
            calc({HEIGHT - SAFE_TOP - SAFE_BOTTOM}px - 100%))); }}
}}

.ln {{ font-family:'NastaliqUrdu','SansArabic',serif; direction:rtl;
  text-align:center; font-size:62px; line-height:2.05;
  /* Nastaliq's descenders hang far below the baseline and the line under them
     is what clips them. This is the number that always needs raising. */
  padding-bottom:10px;
  text-shadow:0 3px 20px rgba(0,0,0,.75), 0 1px 4px rgba(0,0,0,.9); }}

/* Each word starts dim and comes up as the sweep reaches it, so the eye is led
   along the card the way it is when somebody reads to you. It stays up
   afterwards — the line fills rather than flashing one word at a time, and a
   viewer who arrives late still sees everything already read.

   Both properties animate on the WORD, which is what lets the gold below come
   along for the ride without a second animation and a second delay to keep in
   sync with this one. */
.w {{ display:inline-block; color:{p["muted"]}; opacity:.55;
  animation:lit .45s ease forwards; }}

@keyframes lit {{ to {{ color:{p["ink"]}; opacity:1; }} }}

/* The one emphasised word, in the channel's gold — and it OUTRANKS the sweep.
   If every word turned gold in its turn then nothing on the card would be
   emphasised, which throws away the only emphasis this format has. The sweep
   gives the pace; the gold stays the thing worth remembering.
   Only the colour is pinned here: the opacity still comes from the word
   around it, so the gold is dim before its turn and full after, in step with
   everything else. */
em {{ font-style:normal; color:{p["accent"]}; }}
</style>
<div class="scrim"></div>
<div class="brand">{CHANNEL_NAME_UR}</div>
<div class="win"><div class="col">{body}</div></div>
"""
