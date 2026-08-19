"""
templates/scene_islamic.py
The two frames that carry scripture, and nothing else.

Every other scene in a scripture video — the hook, the two explanation scenes,
the action, the follow — is the same frame as the wellness channel's and is
rendered by templates/scene.py. Only the verbatim ones are here, because only
they need a different frame:

  ayah / hadith   The Arabic, alone, centred, in AmiriQuran. No karaoke line,
                  no highlighted word, no icon competing with it. For the
                  Qur'an the audio under this frame is the qari's, so there is
                  nothing to highlight in time with anything; for a hadith the
                  narration line runs along the bottom as a caption while the
                  Arabic holds the middle.

  tarjuma         The Urdu translation as the SUBJECT of the frame rather than
                  as a subtitle under a headline — big Nastaliq, highlighted
                  word by word as the narrator reads it, with the reference
                  above it in small type. The translation is the thing being
                  said; making it the small line under a model-written headline
                  would have got the hierarchy exactly backwards.

The Arabic is set centred and the type is given room: 2.4 line-height and a
generous size floor in FITS below. Uthmani text carries marks above and below
the line, and cramping them is not a matter of taste — the marks collide.
"""
import os

from config import (
    WIDTH, HEIGHT, PALETTE, SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT,
    FONT_DIR, CHANNEL_NAME_UR,
)
from templates.scene import (
    render_scene as render_plain, _font_url, _words_html,
)

# The Arabic is allowed five lines before it starts shrinking, and it does not
# shrink far: 40px is already small for a face this open, and an ayah that will
# not fit at 40px is an ayah too long for a Short — which is a queue decision,
# not a layout one. The translation gets four.
FITS = [(".ar", 5, 40), (".tj", 4, 38), (".cap-box", 2, 30)]


def fits_for(scene: dict) -> list[tuple[str, int, int]]:
    """Which measure-and-shrink rules this scene's layer needs."""
    from templates.scene import FITS as PLAIN_FITS
    return FITS if scene.get("verbatim") else PLAIN_FITS


def render_scene(scene: dict, duration: float, lead: float,
                 index: int, total: int) -> str:
    """One scene of a scripture video."""
    if not scene.get("verbatim"):
        return render_plain(scene, duration, lead, index, total)

    p = PALETTE
    # Gold throughout the verbatim frames, and green nowhere near them. The
    # wellness channel uses colour to separate "problem" from "what to do";
    # here there is one voice on screen and it does not need colour-coding.
    tone = p["accent"]
    pip_w = int(770 / max(total, 1))
    pips = "".join(
        f'<div class="pip{" on" if i < index else ""}'
        f'{" now" if i == index else ""}"></div>' for i in range(total))

    if scene.get("arabic"):
        body = f'<div class="ar">{scene["headline"]}</div>'
        label = f'<div class="cite">{scene.get("citation", "")}</div>'
    else:
        body = (f'<div class="tj">'
                f'{_words_html(scene.get("words") or [], lead)}</div>')
        # On the translation frame the headline IS the reference.
        label = f'<div class="cite">{scene.get("headline", "")}</div>'

    # The narration line only appears where there is one: the Qur'an frame is
    # recited, not narrated, and an empty caption pill in the corner of it
    # would be the sort of leftover UI that makes a video look assembled.
    caption = ""
    if scene.get("arabic") and (scene.get("words") or []):
        caption = (f'<div class="cap"><div class="cap-box">'
                   f'{_words_html(scene["words"], lead)}</div></div>')

    return f"""<!doctype html>
<meta charset="utf-8">
<style>
@font-face {{ font-family:'NastaliqUrdu'; font-weight:400 700;
  src:url('{_font_url("NotoNastaliqUrdu-Bold.ttf")}') format('truetype'); }}
@font-face {{ font-family:'SansArabic'; font-weight:100 900;
  src:url('{_font_url("NotoSansArabic-SemiBold.ttf")}') format('truetype'); }}
/* Static, single-weight, and correct: AmiriQuran is the face the Uthmani
   marks in this text were drawn for. SansArabic stays behind it for anything
   it lacks. */
@font-face {{ font-family:'Quran';
  src:url('{_font_url("AmiriQuran-Regular.ttf")}') format('truetype'); }}

* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ background:transparent; width:{WIDTH}px; height:{HEIGHT}px;
  overflow:hidden; }}
body {{ direction:rtl; color:{p["ink"]}; -webkit-font-smoothing:antialiased;
  /* The whole legibility budget, in one place, and it is spent on the TYPE
   rather than on the picture. Four 2px offsets make a dark outline around
   every glyph — a real -webkit-text-stroke would be centred on the stroke and
   eat Nastaliq's hairlines from both sides, which on this typeface is the
   difference between bold and broken. Then a close drop shadow to lift the
   word off whatever is behind it, and a wide soft one to darken the footage
   immediately around it. This is what lets the background be sharp, bright
   greenery instead of a blurred grey wash. */
--edge:
  2px 0 3px rgba(4,8,14,.95), -2px 0 3px rgba(4,8,14,.95),
  0 2px 3px rgba(4,8,14,.95), 0 -2px 3px rgba(4,8,14,.95),
  0 3px 8px rgba(4,8,14,.9),
  0 6px 30px rgba(4,8,14,.8),
  0 0 60px rgba(4,8,14,.55); }}

/* Light. The ayah sits in the middle of the picture, and what holds it there
   is the outline on the glyphs, not a wash over the footage. This radial only
   settles the middle of the frame a little so a bright sky behind the type does
   not fight the white. Green mountain daylight is the brightest thing this
   channel carries, and it was tested against a worse case than that. */
.scrim {{ position:absolute; inset:0;
  background:
    radial-gradient(120% 70% at 50% 45%, rgba(6,10,18,.32) 0%,
                    rgba(6,10,18,.50) 82%),
    linear-gradient(180deg, rgba(6,10,18,.38) 0%, rgba(6,10,18,0) 24%),
    linear-gradient(0deg,  rgba(6,10,18,.44) 0%, rgba(6,10,18,0) 30%); }}

.brand {{ position:absolute; top:{SAFE_TOP - 74}px; right:{SAFE_RIGHT}px;
  font-family:'NastaliqUrdu','SansArabic',serif; direction:rtl;
  font-size:30px; line-height:1.9; color:rgba(247,250,252,.55); }}

.safe {{ position:absolute;
  top:{SAFE_TOP}px; bottom:{SAFE_BOTTOM}px;
  right:{SAFE_RIGHT}px; left:{SAFE_LEFT}px;
  display:flex; flex-direction:column; }}

.pips {{ display:flex; gap:9px; justify-content:flex-start; margin-bottom:30px; }}
.pip {{ width:{pip_w}px; height:11px; border-radius:6px;
  background:rgba(255,255,255,.28); position:relative; overflow:hidden; }}
.pip.on {{ background:{tone}; box-shadow:0 0 14px {tone}55; }}
.pip.now::after {{ content:''; position:absolute; top:0; bottom:0; right:0;
  width:0; background:{tone}; box-shadow:0 0 14px {tone}55;
  animation:fill {duration:.3f}s linear both paused; }}
@keyframes fill {{ from {{ width:0; }} to {{ width:100%; }} }}

/* Centred in the frame, not anchored to the top like a headline. An ayah is
   not a title for something below it. */
.middle {{ flex:1; display:flex; flex-direction:column;
  align-items:center; justify-content:center; }}

/* A hairline rule above and below rather than a box. A framed card around
   revelation reads as a graphic; two thin lines read as room made for it. */
.rule {{ width:340px; height:2px; opacity:0;
  background:linear-gradient(90deg, transparent, {tone}AA, transparent);
  animation:wide .9s ease-out both paused; }}

.ar {{ font-family:'Quran','SansArabic',serif; direction:rtl;
  font-size:74px;
  /* Uthmani marks sit well above and well below the line. At anything under
     about 2.2 they touch the line above, which on a video nobody can pause is
     simply an error nobody can un-see. */
  line-height:2.4; text-align:center; margin:34px 0;
  text-shadow:var(--edge);
  opacity:0; animation:breathe 1.4s ease-out both paused; }}

.tj {{ font-family:'NastaliqUrdu','SansArabic',serif; font-weight:700;
  direction:rtl; font-size:56px; line-height:2.15; text-align:center;
  margin:34px 0; text-shadow:var(--edge); }}
.tj .w {{ display:inline-block; color:{p["muted"]};
  animation:lit linear forwards paused; }}

.cite {{ font-family:'NastaliqUrdu','SansArabic',serif; direction:rtl;
  font-size:36px; line-height:2.1; color:{tone}; opacity:0;
  text-shadow:var(--edge);
  animation:rise .8s ease-out both paused; animation-delay:.5s; }}

.cap {{ text-align:center; }}
.cap-box {{ display:inline-block; padding:18px 28px 24px; border-radius:20px;
  background:rgba(8,14,24,.72);
  font-family:'NastaliqUrdu','SansArabic',serif; font-weight:700; direction:rtl;
  font-size:40px; line-height:2.05;
  text-shadow:var(--edge); }}
.cap-box .w {{ display:inline-block; color:{p["muted"]};
  animation:lit linear forwards paused; }}

/* Same trick as the wellness caption: `forwards`, so an unspoken word keeps
   its muted colour instead of being lit from frame zero. */
@keyframes lit {{
  0%   {{ color:{tone}; text-shadow:var(--edge), 0 0 26px {tone}66; }}
  70%  {{ color:{tone}; text-shadow:var(--edge), 0 0 26px {tone}66; }}
  100% {{ color:{p["ink"]}; text-shadow:var(--edge); }} }}
/* The ayah does not slide in from anywhere. It fades up and settles from a
   hair oversize — the slowest entrance in the whole video, because this is
   the frame the video was made to show. */
@keyframes breathe {{ from {{ opacity:0; transform:scale(1.05); }}
                      to   {{ opacity:1; transform:none; }} }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(24px); }}
                   to   {{ opacity:1; transform:none; }} }}
@keyframes wide {{ from {{ opacity:0; transform:scaleX(.2); }}
                   to   {{ opacity:.9; transform:none; }} }}
</style>
<div class="scrim"></div>
<div class="brand">{CHANNEL_NAME_UR}</div>
<div class="safe">
  <div class="pips">{pips}</div>
  <div class="middle">
    <div class="rule"></div>
    {body}
    <div class="rule"></div>
    {label}
  </div>
  {caption}
</div>
"""
