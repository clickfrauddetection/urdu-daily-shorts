"""
replicate_bg.py
The background when Pixabay has nothing: generate one instead.

Two modes, and the default is the cheap one on purpose.

  "still" (default) — one FLUX image, turned into a short loopable clip. The
      motion comes from the sine drift assembler.compose_scene already applies
      to every background. That drift is free, never distorts, and looks the
      same on a still as it does on footage. ~$0.003 a video.

  "motion" — the FLUX still, then LTX-Video animates ~4s of it. ~$0.057 a
      video, twenty times the still, and worth knowing before switching it on:
      tiktok-reels-agent ran this and turned it OFF (its MOTION_MAX_SCENES
      defaults to 0) because the clips came back uneven and one visibly spoiled
      a published video. Set REPLICATE_BG_MODE=motion to try it anyway.

Either way the result is ONE clip that loops under the whole video, exactly
like the Pixabay path — so nothing downstream knows or cares where the
background came from.

Never fatal. This is already the fallback; a fallback that can take down the
run is worse than no fallback, and assembler.py's flat gradient is behind it.
"""
import os
import subprocess
import time

import requests

from config import (
    REPLICATE_API_KEY, REPLICATE_BG_MODE, WIDTH, HEIGHT, FPS, TEMP_DIR,
    IMAGE_GEN_TIMEOUT, MOTION_GEN_TIMEOUT, IMAGE_GEN_RETRIES,
)

# The version hash is NOT optional on the second one. Replicate resolves a bare
# "owner/name" against POST /v1/models/{owner}/{name}/predictions, and that
# endpoint exists ONLY for Replicate's *official* models. flux-schnell is
# official, so the bare name is correct. lightricks/ltx-video is a community
# model — unpinned it returns 404 "The requested resource could not be found"
# on every single call, which is how it silently never worked in the sibling
# repo for the entire time it was enabled.
FLUX_MODEL = "black-forest-labs/flux-schnell"
MOTION_MODEL = (
    "lightricks/ltx-video:"
    "8c47da666861d081eeb4d1261853087de23923a268a69b63febdf5dc1dee08e4"
)

# What the generated background should be, per PILLAR — the same reason
# stock_bg.THEMES is keyed that way. Dark and calm, because type sits on top.
PILLAR_PROMPT = {
    "neend": ("a calm dark night scene, moonlight through a window onto an "
              "empty quiet room, deep blue tones, soft shadows"),
    "paisa": ("a city skyline at blue hour seen from a high window, deep blue "
              "and amber tones"),
    "waqt": ("a quiet desk by a window at first light, warm soft rim light, "
             "shallow depth of field, calm and uncluttered"),
    "phone": ("a dark room lit only by a faint cool screen glow, deep blue "
              "tones, soft bokeh"),
    "ghar": ("morning sunlight through a curtain onto a simple tidy room, warm "
             "soft tones, a plant by the window"),
    "aadat": ("an empty park path at sunrise, mist and long shadows, cool "
              "morning tones"),
    "rishtay": ("a warm evening room with soft lamp light, two empty chairs, "
                "amber tones"),
    "sleep": ("a calm dark night scene, moonlight through a window onto an "
              "empty quiet room, deep blue tones"),
    "warzish": ("an empty park path at sunrise, mist and long shadows, cool "
                "morning tones, no people"),
    "khurak": ("a simple kitchen window at morning, a glass of water on a "
               "wooden table, warm soft light, no people"),
    "usool": ("a quiet desk by a window at first light, a closed notebook, "
              "warm rim light, uncluttered, no people"),
    # No mosque interiors, no calligraphy, no Arabic text of any kind in a
    # GENERATED image: an image model asked for Arabic script produces
    # letter-shaped noise, and letter-shaped noise behind an ayah is the worst
    # thing this channel could put on screen. Landscape and light only, and the
    # same green mountain country the Pixabay themes look for.
    "quran": ("a wide green alpine meadow below snow-capped peaks, soft morning "
              "light, drifting cloud, no people, no buildings, no text"),
    "hadith": ("a clear mountain stream through green pines, soft light through "
               "the canopy, mist, no people, no buildings, no text"),
    "default": ("a calm dark atmospheric landscape at night, deep blue tones, "
                "soft moonlight"),
}

# Appended to every prompt above. No people and no faces: a recognisable
# stock-looking face on a daily channel reads as fake within three posts, and
# generated faces read as fake immediately.
PROMPT_SUFFIX = ", cinematic, vertical, no people, no faces, no text"

MOTION_PROMPT = "very slow gentle camera drift, subtle ambient movement, calm"

STILL_SECONDS = 4.0   # long enough that the loop is not obvious under the drift


def available() -> bool:
    return bool(REPLICATE_API_KEY)


def _call(fn, timeout, *args, **kwargs):
    """Run `fn` with a hard wall-clock bound.

    Replicate occasionally hangs for minutes under provider load, and a request
    timeout does not cover a call that is progressing slowly forever. The
    thread is a daemon so a genuinely stuck call cannot block process exit — it
    is simply abandoned.
    """
    import threading
    box = {}

    def _runner():
        try:
            box["value"] = fn(*args, **kwargs)
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"Replicate call exceeded {timeout}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _flux_still(prompt: str, out_path: str) -> str | None:
    import replicate
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY

    for attempt in range(1, IMAGE_GEN_RETRIES + 1):
        try:
            output = _call(replicate.run, IMAGE_GEN_TIMEOUT, FLUX_MODEL, input={
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "output_format": "png",
                "num_outputs": 1,
            })
            url = str(output[0]) if isinstance(output, (list, tuple)) else str(output)
            with open(out_path, "wb") as f:
                f.write(requests.get(url, timeout=120).content)
            return out_path
        except Exception as e:
            print(f"    FLUX attempt {attempt}/{IMAGE_GEN_RETRIES}: {e}")
            if attempt < IMAGE_GEN_RETRIES:
                # Rising, not flat: the 404s and "no adapter found" errors
                # Replicate returns under load clear in tens of seconds, and
                # three retries three seconds apart all land in the same bad
                # window.
                time.sleep(3 * (2 ** (attempt - 1)))
    return None


def _ltx_motion(image_path: str, out_path: str) -> str | None:
    import replicate
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY

    for attempt in range(1, IMAGE_GEN_RETRIES + 1):
        try:
            with open(image_path, "rb") as img:
                output = _call(replicate.run, MOTION_GEN_TIMEOUT, MOTION_MODEL,
                               input={
                                   "image": img,
                                   "prompt": MOTION_PROMPT,
                                   "length": 97,          # ~4s at the model's 24fps
                                   "target_size": 640,
                                   "image_noise_scale": 0.12,
                               })
            url = str(output[0]) if isinstance(output, (list, tuple)) else str(output)
            with open(out_path, "wb") as f:
                f.write(requests.get(url, timeout=180).content)
            return out_path
        except Exception as e:
            print(f"    LTX attempt {attempt}/{IMAGE_GEN_RETRIES}: {e}")
            if attempt < IMAGE_GEN_RETRIES:
                time.sleep(3 * (2 ** (attempt - 1)))
    return None


def _still_to_clip(image_path: str, out_path: str) -> str:
    """Wrap the still in a short clip so it loops like any other background."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", image_path, "-t", f"{STILL_SECONDS:.2f}",
         # Scaled to fill with a margin, because compose_scene's drift crops
         # into it — handing it an exactly-sized frame would drift off the edge.
         "-vf", f"scale={int(WIDTH * 1.2)}:{int(HEIGHT * 1.2)}:"
                f"force_original_aspect_ratio=increase,fps={FPS}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", out_path],
        check=True, capture_output=True)
    return out_path


def fetch(pillar: str, out_path: str | None = None) -> str | None:
    """Generate the background clip. None if it could not be made."""
    if not available():
        print("  REPLICATE_API_TOKEN not set — no generated fallback")
        return None

    os.makedirs(TEMP_DIR, exist_ok=True)
    out_path = out_path or f"{TEMP_DIR}/bg_generated.mp4"
    still = f"{TEMP_DIR}/bg_still.png"
    prompt = PILLAR_PROMPT.get(pillar, PILLAR_PROMPT["default"]) + PROMPT_SUFFIX

    print(f"  generating a background instead ({REPLICATE_BG_MODE})")
    if not _flux_still(prompt, still):
        print("  FLUX could not produce a still — flat gradient background")
        return None

    if REPLICATE_BG_MODE == "motion":
        clip = _ltx_motion(still, f"{TEMP_DIR}/bg_motion.mp4")
        if clip:
            print("  background: generated motion clip")
            return clip
        # Not a failure worth losing the background over — the still is already
        # made and paid for, and the drift will animate it anyway.
        print("  LTX failed — using the still with the drift instead")

    print("  background: generated still, animated by the compositor's drift")
    return _still_to_clip(still, out_path)
