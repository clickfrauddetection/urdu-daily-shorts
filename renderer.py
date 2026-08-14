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
a screenshot. A 7.00s scene is 210 frames at 30fps on any machine, so the
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


def render_layer(html: str, name: str, duration: float) -> str:
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

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
         # Downscale from the 2x render. lanczos is the only filter here worth
         # arguing about: bilinear softens Nastaliq's hairlines into mush.
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

            for i in range(frames):
                page.evaluate(_SEEK, (i / FPS) * 1000)
                ff.stdin.write(page.screenshot(
                    type="png", omit_background=True, animations="disabled"))

            ctx.close()
            browser.close()
    finally:
        if ff.stdin:
            ff.stdin.close()
        err = ff.stderr.read().decode(errors="replace")
        if ff.wait() != 0:
            raise RuntimeError(f"ffmpeg failed encoding {name}: {err[-600:]}")

    print(f"  {name}: {frames} frames / {duration:.2f}s")
    return out


def probe_fonts() -> None:
    """Fail loudly if the Urdu fonts are missing, before anything is rendered.

    Called once at startup. Without this the run completes, the video ships,
    and the Urdu silently falls back to a Latin font that draws every letter
    as a box — a failure that looks like success in every log line.
    """
    from config import FONT_DIR
    required = ["NotoNastaliqUrdu-Bold.ttf", "NotoSansArabic-SemiBold.ttf"]
    missing = [f for f in required
               if not os.path.exists(os.path.join(FONT_DIR, f))]
    if missing:
        raise RuntimeError(
            "Urdu fonts missing from ./fonts: " + ", ".join(missing)
            + "\nRun: python fetch_fonts.py"
        )
