"""
stock_bg.py
One looping background clip per video, from Pixabay's free Video API.

One clip for the WHOLE video, not one per scene. Scenes cut on the text layer
while the footage runs continuously underneath, which is why assembler.py can
hard-cut between scenes with no crossfade and still look seamless — and why
there is no per-scene image bill. Free tier, ~100 requests/60s, nowhere near
one video a day.

The query never comes from the writer's imagination. A model asked to invent a
search term returns things like "circadian rhythm visualisation", Pixabay
returns nothing, and the video ships on a flat gradient. It picks from a fixed
list per niche instead, every entry of which is a term stock footage actually
exists for.
"""
import os
import random

import requests

from config import PIXABAY_API_KEY, TEMP_DIR

PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"
SIZE_PREFERENCE = ["large", "medium", "small", "tiny"]

# Calm, slow, loopable, and — the constraint that matters — nothing with a
# recognisable face. A stock actor's face on a daily channel reads as a stock
# video within three posts, and viewers stop trusting the account.
THEMES = {
    "sleep": ["night sky stars", "moon clouds night", "calm bedroom window",
              "rain on window night", "city lights night timelapse",
              "candle flame dark", "fog forest morning"],
    "focus": ["desk sunlight morning", "coffee pour slow motion",
              "book pages turning", "rain window desk", "clock ticking macro"],
    "money": ["city skyline timelapse", "market street busy", "coins macro",
              "office window evening", "traffic timelapse night"],
    "fitness": ["running shoes road", "mountain trail sunrise",
                "water pouring glass", "park path morning", "ocean waves slow"],
    "default": ["clouds timelapse", "ocean waves slow", "forest light rays",
                "rain on window night", "mountain sunrise"],
}


def theme_for(niche: str) -> str:
    return random.choice(THEMES.get(niche, THEMES["default"]))


def _best_file(hit: dict) -> str | None:
    videos = hit.get("videos", {})
    for size in SIZE_PREFERENCE:
        url = videos.get(size, {}).get("url")
        if url:
            return url
    return None


def fetch(query: str, out_path: str | None = None) -> str | None:
    """Download a background clip, or return None so the run continues.

    None rather than an exception on purpose: assembler.py falls back to a
    brand gradient, and a missing background is not a reason to lose the day's
    video. It is printed loudly instead — a channel silently running on flat
    gradients for a week is the failure to actually worry about.
    """
    if not PIXABAY_API_KEY:
        print("  PIXABAY_API_KEY not set — background will be a flat gradient")
        return None

    out_path = out_path or f"{TEMP_DIR}/bg.mp4"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    try:
        resp = requests.get(PIXABAY_VIDEO_URL, params={
            "key": PIXABAY_API_KEY, "q": query, "video_type": "film",
            "safesearch": "true", "per_page": 30,
        }, timeout=30)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"  Pixabay lookup failed ({e}) — flat gradient background")
        return None

    # Prefer clips long enough that the loop point is not obvious inside a
    # 60-second video. Anything under ~10s wraps often enough to be noticed.
    long_hits = [h for h in hits if h.get("duration", 0) >= 12]
    ordered = long_hits + [h for h in hits if h not in long_hits]

    for hit in ordered:
        url = _best_file(hit)
        if not url:
            continue
        try:
            with requests.get(url, stream=True, timeout=90) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
        except Exception as e:
            print(f"  background download failed ({e}) — trying the next hit")
            continue
        print(f"  background: {query!r} ({hit.get('duration', '?')}s, "
              f"id {hit.get('id')})")
        return out_path

    print(f"  no usable Pixabay clip for {query!r} — flat gradient background")
    return None
