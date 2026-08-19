"""
renderer.py
Deterministic frame-by-frame capture of an HTML layer, with alpha.

This is the part that is deliberately NOT how the sibling repos do it. They use
Playwright's `record_video`, which produces a variable-frame-rate webm on the
wall clock: the file always comes back a little shorter than the time it was
recorded over, and how much shorter depends on how fast the machine is. Every
`tpad=stop_mode=clone`, every measured `lead` offset, every "the closing screen
is three seconds adrift of the words describing it" fix in those repos is a
patch on that one fact. On a slow CI runner the patches stop holding.

Here the browser's clock is never used. Animations are authored paused, and
each frame is produced by seeking every animation to an exact time and taking
a screenshot. A 7.00s scene is the same frame count on any machine, so the
narration offsets computed in main.py are true by construction and no padding
is ever needed.

The frames carry alpha (`omit_background`) and are piped straight into ffmpeg
as a lossless QuickTime RLE .mov — nothing touches the disk as loose PNGs. The
background footage is composited underneath in ffmpeg (see assembler.py),
never inside the browser: a <video> element decoded by Chromium cannot be
seeked frame-accurately, which would put the drift straight back in.
"""
import os
import subprocess
import time

from playwright.sync_api import sync_playwright

from config import WIDTH, HEIGHT, FPS, SCALE, TEMP_DIR

# Subpixel antialiasing paints coloured fringes on glyph edges. They are
# invisible on a desktop LCD and very visible after H.264 chews on thin Urdu
# strokes, so text is rendered greyscale-antialiased instead.
CHROMIUM_ARGS = [
    "--disable-lcd-text",
    "--font-render-hinting=none",
    "--force-color-profile=srgb",
    "--disable-gpu",
]

# Fonts, the logo and the first layout have to be settled before frame zero.
# This is not a race we are timing against — the clock is frozen either way —
# it is just making sure the paint is complete.
SETTLE_MS = 400

_SEEK = """
(ms) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms; }
}
"""

# Ported from tiktok-reels-agent's scene_renderer.py, which had the right idea:
# an Urdu line's width cannot be guessed, because it depends on which letters
# join to which. Picking a font size that fits the AVERAGE sentence means every
# other sentence is either overflowing or swimming in space. The page measures
# its own text instead and steps the size down one pixel at a time until it
# fits — exact for every sentence rather than right for the mean one.
_FIT = """
([sel, maxLines, minPx]) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  // scrollHeight includes the element's own padding. Comparing it against
  // lineHeight * maxLines counts that padding as if it were another line and
  // shrinks text that already fits.
  const lines = () => {
    const cs = getComputedStyle(el);
    const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
    return Math.round((el.scrollHeight - pad) / parseFloat(cs.lineHeight));
  };
  let size = parseFloat(getComputedStyle(el).fontSize);
  let guard = 0;
  while (lines() > maxLines && size > minPx && guard++ < 80) {
    size -= 1;
    el.style.fontSize = size + 'px';
  }
  return {px: Math.round(size), lines: lines()};
}
"""


def render_layer(html: str, name: str, duration: float,
                 fits: list[tuple[str, int, int]] | None = None) -> str:
    """Render `html` for `duration` seconds and return an alpha .mov path.

    The HTML must have a transparent html/body background and must author its
    animations with `animation-play-state: paused` and `animation-fill-mode:
    both` — paused so nothing advances during load, `both` so seeking to a
    time inside an animation-delay shows the from-state rather than the
    element's static state.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    html_path = os.path.abspath(os.path.join(TEMP_DIR, f"{name}.html"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    out = os.path.join(TEMP_DIR, f"{name}.mov")
    frames = max(1, round(duration * FPS))
    t_start = time.monotonic()

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
         # A no-op at SCALE=1; the downscale path when SCALE is raised. lanczos
         # is the only filter here worth arguing about — bilinear softens
         # Nastaliq's hairlines into mush.
         "-vf", f"scale={WIDTH}:{HEIGHT}:flags=lanczos",
         "-c:v", "qtrle", "-pix_fmt", "argb", out],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=CHROMIUM_ARGS)
            ctx = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                device_scale_factor=SCALE,
                # A page that asks for reduced motion gets none of the
                # animation this whole module exists to capture.
                reduced_motion="no-preference",
            )
            page = ctx.new_page()
            page.goto(f"file:///{html_path.replace(os.sep, '/')}")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(SETTLE_MS)

            # After the fonts land, never before — the measurement is of the
            # real typeface, and against a fallback face it is measuring the
            # wrong glyph widths entirely.
            for sel, max_lines, min_px in (fits or []):
                got = page.evaluate(_FIT, [sel, max_lines, min_px])
                if got and got["lines"] > max_lines:
                    print(f"  {name}: {sel} still {got['lines']} lines at the "
                          f"{min_px}px floor — the text is too long, not too big")

            # A scene is a few hundred screenshots and takes tens of seconds.
            # Without a heartbeat the CI log shows nothing at all between
            # scenes, which is indistinguishable from a hang — and that is
            # exactly how the first run read.
            mark = max(frames // 4, 1)
            t0 = time.monotonic()
            for i in range(frames):
                if i and i % mark == 0:
                    print(f"    {name}: {100 * i // frames}% "
                          f"({time.monotonic() - t0:.0f}s)", flush=True)
                page.evaluate(_SEEK, (i / FPS) * 1000)
                # NOT animations="disabled". That option does not freeze an
                # animation where it is — it fast-forwards every animation to
                # its final state before the shot. With it on, every frame came
                # back fully animated: the icon drawn, the headline landed, and
                # every caption word already lit, which reads as a static
                # subtitle and is exactly the effect this module exists for.
                # We have already paused and seeked; there is nothing to
                # stabilise.
                ff.stdin.write(page.screenshot(type="png", omit_background=True))

            ctx.close()
            browser.close()
    finally:
        if ff.stdin:
            ff.stdin.close()
        err = ff.stderr.read().decode(errors="replace")
        if ff.wait() != 0:
            raise RuntimeError(f"ffmpeg failed encoding {name}: {err[-600:]}")

    print(f"  {name}: {frames} frames / {duration:.2f}s "
          f"in {time.monotonic() - t_start:.0f}s", flush=True)
    return out


def probe_fonts() -> None:
    """Fail loudly if the Urdu fonts are missing, before anything is rendered.

    Called once at startup. Without this the run completes, the video ships,
    and the Urdu silently falls back to a Latin font that draws every letter
    as a box — a failure that looks like success in every log line.
    """
    from config import FONT_DIR, CONTENT_KIND
    required = ["NotoNastaliqUrdu-Bold.ttf", "NotoSansArabic-SemiBold.ttf"]
    # Any channel that can have a scripture day puts Uthmani text on screen,
    # so its face is not optional — a missing AmiriQuran would fall back to the
    # sans and publish an ayah in the wrong script style, which is the same
    # class of silent success this function was written to prevent. Checked on
    # every run, including habit days: the point is to fail before a build, not
    # on the morning the alternation happens to land on scripture.
    if CONTENT_KIND != "habit":
        required.append("AmiriQuran-Regular.ttf")
    missing = [f for f in required
               if not os.path.exists(os.path.join(FONT_DIR, f))]
    if missing:
        raise RuntimeError(
            "Urdu fonts missing from ./fonts: " + ", ".join(missing)
            + "\nRun: python fetch_fonts.py"
        )
