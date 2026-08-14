"""
templates/scene.py
One scene's text layer: transparent, right-to-left, safe-zone aware.

Everything here is drawn over the background footage, so the layer carries its
own scrim — a top-and-bottom gradient that guarantees the type is readable on
whatever clip Pixabay returned that morning. Without it, a video's legibility
is decided by a stock clip nobody looked at.

Nastaliq for both the headline and the caption. The caption started on Noto
Sans Arabic, which is the easier face to read small and moving — but in a
finished video the sans line read as a machine subtitle bolted under Urdu type,
and the frame stopped looking like an Urdu video at all. It is carried smaller
and with much more leading to pay for that: Nastaliq's descenders sit far below
the baseline, and at anything under about 2.0 the lines clip into each other.
Noto Sans Arabic stays loaded as the fallback for characters Nastaliq lacks.

Animations are authored `paused` with `fill: both` because renderer.py seeks
them frame by frame; see the note there before changing any timing here.
"""
import os

from config import (
    WIDTH, HEIGHT, PALETTE, SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT,
    FONT_DIR,
)
from icons import icon, ROLE_DEFAULT


# Ported from the reels repo. Captions cap at two lines and the headline at
# three: a third stacked line of Nastaliq stops reading as type and starts
# covering the picture. renderer.render_layer measures and shrinks to fit.
FITS = [(".h", 3, 54), (".cap-box", 2, 32)]

MIN_WORD_DURATION = 0.12  # so a very short or mistimed word still flashes


def script_of(text: str, face: str = "display") -> tuple[str, str]:
    """Writing direction and font family, decided by the text's own script.

    `face` picks which Urdu typeface: "display" is Nastaliq, for the headline
    only — it is the shape a reader stops for, and it is genuinely hard to read
    small and moving. "body" is Noto Sans Arabic, for the caption, which is
    small, moving, and has to be legible at a glance or it is not a caption.

    The reels repo learned this the expensive way: it hard-coded direction:rtl
    for Urdu, then its content engine started returning Roman Urdu and every
    line rendered with its words visually reversed — full stops leading the
    line, unreadable — and that is what shipped. This repo has the same
    exposure, and worse: data/topics.json is written in Roman Urdu, so a model
    that echoes the topic instead of translating it produces exactly that
    input. Latin text is laid out left-to-right in a font that actually has
    Latin glyphs, so a wrong-script line degrades to off-brand instead of to
    nonsense.
    """
    urdu = any("؀" <= ch <= "ۿ" or "ﭐ" <= ch <= "﷿"
               or "ﹰ" <= ch <= "﻿" for ch in text)
    if urdu:
        # Nastaliq for BOTH now. The caption started on Noto Sans Arabic for
        # legibility, and it is genuinely the easier face to read small — but
        # side by side in a finished video the sans caption reads as a machine
        # subtitle bolted under Urdu type, and the whole frame stops looking
        # like an Urdu video. It is carried at a larger size and a much taller
        # line-height below to pay for the difference.
        return "rtl", "'NastaliqUrdu', 'SansArabic', serif"
    return "ltr", "Arial, Helvetica, sans-serif"


def _font_url(filename: str) -> str:
    path = os.path.abspath(os.path.join(FONT_DIR, filename))
    return "file:///" + path.replace(os.sep, "/")


def _words_html(words: list, lead: float) -> str:
    """The karaoke line: each word lights up as it is spoken.

    `lead` shifts every word by the scene's own start pad, because the voice
    clip is laid into the scene after that pad and the highlight has to agree
    with it. Getting this wrong is not subtle — the caption runs ahead of the
    narrator for the entire scene, which is the bug the reels repo shipped for
    weeks before `b602eea`.
    """
    out = []
    for w, start, end in words:
        dur = max(end - start, MIN_WORD_DURATION)
        out.append(
            f'<span class="w" style="animation-delay:{start + lead:.3f}s;'
            f'animation-duration:{dur:.3f}s">{w}</span>'
        )
    return " ".join(out)


def render_scene(scene: dict, duration: float, lead: float,
                 index: int, total: int) -> str:
    """`scene` needs: role, headline, words. `icon` is optional."""
    name = scene.get("icon") or ROLE_DEFAULT[scene["role"]]
    p = PALETTE
    # The hook scene gets the accent; tactic scenes get the green so a viewer
    # can tell "here is the problem" from "here is what to do" without reading.
    tone = p["accent"] if scene["role"] in ("hook", "problem", "cause") else p["accent_2"]

    # Decided per scene, from the text that actually arrived, not once for the
    # repo. A script that ships one Roman Urdu headline among seven Urdu ones
    # should get one left-to-right headline, not a reversed one.
    h_dir, h_font = script_of(scene["headline"], "display")
    cap_text = " ".join(w for w, _, _ in (scene.get("words") or []))
    c_dir, c_font = script_of(cap_text, "body")

    return f"""<!doctype html>
<meta charset="utf-8">
<style>
/* Both files are VARIABLE fonts with a wght axis. The weight has to be
   declared as a RANGE, not as a single value: telling the browser "this file
   is 700" makes it treat the file as one static weight and render the axis
   default instead — which is 400, and looks like the wrong font rather than
   like a bug. The range lets font-weight below actually select an instance. */
@font-face {{ font-family:'NastaliqUrdu'; font-weight:400 700;
  src:url('{_font_url("NotoNastaliqUrdu-Bold.ttf")}') format('truetype'); }}
@font-face {{ font-family:'SansArabic'; font-weight:100 900;
  src:url('{_font_url("NotoSansArabic-SemiBold.ttf")}') format('truetype'); }}

* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ background:transparent; width:{WIDTH}px; height:{HEIGHT}px;
  overflow:hidden; }}
body {{ direction:rtl; color:{p["ink"]}; -webkit-font-smoothing:antialiased; }}

/* Scrim. Two gradients rather than a flat wash: the middle of the frame stays
   open so the footage is still visible, while the bands the type sits in are
   dark enough to hold contrast on a bright clip. */
.scrim {{ position:absolute; inset:0;
  background:
    linear-gradient(180deg, rgba(6,10,18,.80) 0%, rgba(6,10,18,0) 34%),
    linear-gradient(0deg,  rgba(6,10,18,.88) 0%, rgba(6,10,18,0) 42%); }}

.safe {{ position:absolute;
  top:{SAFE_TOP}px; bottom:{SAFE_BOTTOM}px;
  right:{SAFE_RIGHT}px; left:{SAFE_LEFT}px;
  display:flex; flex-direction:column; }}

/* progress pips — how far through the video the viewer is, which measurably
   holds people who would otherwise bail at the halfway mark */
.pips {{ display:flex; gap:9px; justify-content:flex-start; margin-bottom:30px; }}
.pip {{ width:{int(770 / max(total, 1))}px; height:11px; border-radius:6px;
  background:rgba(255,255,255,.28); }}
.pip.on {{ background:{tone}; box-shadow:0 0 14px {tone}55; }}

/* Anchored to the top of the safe box, not centred in it. Centred, the
   headline floated in the middle of the frame with a third of the picture
   empty above the caption — which is what the first live video looked like. */
.top {{ flex:1; display:flex; flex-direction:column;
  align-items:flex-start; justify-content:flex-start; padding-top:120px; }}

/* The icon sits in a tinted disc rather than floating as a thin outline. A
   2px stroke alone over moving footage reads as a stray mark; the disc gives
   it a ground, ties it to the scene's colour, and survives a bright frame. */
.ic-wrap {{ display:flex; align-items:center; justify-content:center;
  width:200px; height:200px; border-radius:50%;
  background:{tone}1F; border:3px solid {tone}59;
  opacity:0; filter:drop-shadow(0 8px 26px rgba(0,0,0,.55));
  animation:pop .55s cubic-bezier(.2,.9,.3,1.3) both paused; }}
.ic {{ color:{tone}; }}
/* No stroke-draw. It used a fixed dasharray of 140, which is longer than some
   of these paths and shorter than others, so the icon spent its first second
   as a partial outline — in the first live video the hook's phone icon opened
   as an empty rectangle, which is the single worst thing to put in frame one.
   The pop is enough movement on its own. */

.h {{ font-family:{h_font}; font-weight:700; direction:{h_dir};
  font-size:{scene.get("headline_size", 92)}px;
  /* Nastaliq descenders run deep; below ~2.1 the tails of one line are cut by
     the next. This is the number that most often needs raising, never lowering. */
  line-height:2.15;
  margin-top:20px; text-align:{"right" if h_dir == "rtl" else "left"};
  text-shadow:0 4px 26px rgba(0,0,0,.75);
  opacity:0; animation:rise .7s cubic-bezier(.2,.8,.3,1) both paused;
  animation-delay:.28s; }}
.h em {{ font-style:normal; color:{tone}; }}

/* the spoken line, lower third, inside the safe box */
.cap {{ text-align:center; }}
/* A tinted pill behind the words, ported from the reels repo. The scrim alone
   holds contrast on most clips; the pill holds it on all of them, including the
   bright ones nobody looked at before the video published. */
.cap-box {{ display:inline-block; padding:20px 30px 26px; border-radius:20px;
  background:rgba(8,14,24,.72);
  font-family:{c_font}; font-weight:700; direction:{c_dir};
  /* Nastaliq, so: smaller than the sans caption was, and far more leading.
     Its descenders run deep and two lines at 1.85 clipped into each other. */
  font-size:46px; line-height:2.05;
  text-shadow:0 3px 18px rgba(0,0,0,.85); }}
/* `forwards`, not `both`, and this is the whole trick of the karaoke line: with
   `both` the word would hold the from-state before its delay, which is the same
   colour it ends on — every word lit from frame zero. With `forwards` an
   un-started word keeps its own muted colour, flares accent as it is said, and
   stays bright afterwards, so the line reads as a filling progress bar. */
.cap-box .w {{ display:inline-block; color:{p["muted"]};
  animation:lit linear forwards paused; }}

/* The flare is on the word's FIRST frame, held, then cooled — not ramped into.
   Ramping over the first 30% put the highlight ~90ms behind the voice on a
   typical word, which reads as a sync fault rather than as a style. The reels
   repo shipped exactly that and fixed it the same way; the cool-down afterwards
   can stay slow, because a trailing word settling is not something the ear
   tracks. */
@keyframes lit {{
  0%   {{ color:{tone}; text-shadow:0 0 26px {tone}66, 0 3px 18px rgba(0,0,0,.85); }}
  70%  {{ color:{tone}; text-shadow:0 0 26px {tone}66, 0 3px 18px rgba(0,0,0,.85); }}
  100% {{ color:{p["ink"]}; text-shadow:0 3px 18px rgba(0,0,0,.85); }} }}
@keyframes pop  {{ from {{ opacity:0; transform:scale(.6) translateY(20px); }}
                   to   {{ opacity:1; transform:none; }} }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(38px); }}
                   to   {{ opacity:1; transform:none; }} }}
</style>
<div class="scrim"></div>
<div class="safe">
  <div class="pips">
    {"".join(f'<div class="pip{" on" if i <= index else ""}"></div>'
             for i in range(total))}
  </div>
  <div class="top">
    <div class="ic-wrap">{icon(name, 110)}</div>
    <div class="h">{scene["headline"]}</div>
  </div>
  <div class="cap"><div class="cap-box">{
      _words_html(scene.get("words") or [], lead)}</div></div>
</div>
"""
