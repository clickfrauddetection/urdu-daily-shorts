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
import time

import requests

from config import PIXABAY_API_KEY, TEMP_DIR

PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"
SIZE_PREFERENCE = ["large", "medium", "small", "tiny"]

# Calm, slow, loopable, and — the constraint that matters — nothing with a
# recognisable face. A stock actor's face on a daily channel reads as a stock
# video within three posts, and viewers stop trusting the account.
# Keyed by PILLAR, not by channel. A broad channel runs a money topic on
# Tuesday and a sleep topic on Wednesday, and one shared theme list would open
# both on a night sky — which tells the viewer, in the first second, that the
# picture has nothing to do with the words.
THEMES = {
    "neend": ["night sky stars", "moon clouds night", "calm bedroom window",
              "rain on window night", "candle flame dark", "fog forest morning"],
    "paisa": ["city skyline timelapse", "market street busy", "coins macro",
              "office window evening", "shopping street evening"],
    "waqt": ["clock ticking macro", "desk sunlight morning", "sand timer",
             "book pages turning", "traffic timelapse day"],
    "phone": ["city lights night timelapse", "rain window desk",
              "abstract light bokeh", "dark room screen glow"],
    "ghar": ["sunlight through curtains", "calm bedroom window",
             "plant leaves sunlight", "kitchen window morning"],
    "aadat": ["park path morning", "running shoes road", "water pouring glass",
              "mountain trail sunrise", "ocean waves slow"],
    "rishtay": ["sunset field warm", "tea cup steam", "park bench evening",
                "warm light window"],
    # Kept for the older flat niches.
    "sleep": ["night sky stars", "moon clouds night", "calm bedroom window",
              "rain on window night", "candle flame dark"],
    "default": ["clouds timelapse", "ocean waves slow", "forest light rays",
                "rain on window night", "mountain sunrise"],
}


# Tried after the niche's own themes are exhausted. Deliberately generic: at
# this point the goal is any calm, dark, loopable clip at all, because the
# alternative is a flat gradient.
LAST_RESORT = ["night", "clouds", "nature", "abstract dark"]

ATTEMPTS_PER_QUERY = int(os.environ.get("PIXABAY_ATTEMPTS") or 3)
BACKOFF = 3.0


def theme_for(niche: str) -> str:
    return random.choice(THEMES.get(niche, THEMES["default"]))


def _candidates(niche: str) -> list[str]:
    """Every query worth trying, best first.

    The niche's own themes come first, shuffled so consecutive days do not open
    on the same clip, then the generic ones. Pixabay's API is genuinely flaky —
    it times out and 5xxs often enough that a single query with a single
    attempt loses the background on a normal week — and one query failing says
    nothing about the next one.
    """
    themes = list(THEMES.get(niche, THEMES["default"]))
    random.shuffle(themes)
    return themes + LAST_RESORT


def _best_file(hit: dict) -> str | None:
    videos = hit.get("videos", {})
    for size in SIZE_PREFERENCE:
        url = videos.get(size, {}).get("url")
        if url:
            return url
    return None


def _search(query: str) -> list[dict]:
    """Search results for one query, retried. [] if the query is exhausted."""
    for attempt in range(1, ATTEMPTS_PER_QUERY + 1):
        try:
            resp = requests.get(PIXABAY_VIDEO_URL, params={
                "key": PIXABAY_API_KEY, "q": query, "video_type": "film",
                "safesearch": "true", "per_page": 30,
            }, timeout=30)
        except Exception as e:
            print(f"    {query!r} attempt {attempt}: {type(e).__name__}")
            if attempt < ATTEMPTS_PER_QUERY:
                time.sleep(BACKOFF * attempt)
            continue

        # A bad or rate-limited key is not a query problem, and trying twenty
        # more queries against it just burns the run's clock for nothing.
        if resp.status_code in (400, 401, 403, 429):
            raise RuntimeError(
                f"Pixabay rejected the key (HTTP {resp.status_code}): "
                f"{resp.text[:160]}")
        if resp.status_code >= 500:
            print(f"    {query!r} attempt {attempt}: HTTP {resp.status_code}")
            if attempt < ATTEMPTS_PER_QUERY:
                time.sleep(BACKOFF * attempt)
            continue

        try:
            return resp.json().get("hits", [])
        except ValueError:
            if attempt < ATTEMPTS_PER_QUERY:
                time.sleep(BACKOFF * attempt)
    return []


def _download(hits: list[dict], out_path: str) -> dict | None:
    """First hit that actually downloads. Long clips first."""
    # Long enough that the loop point is not obvious inside a 60-second video.
    # Anything under ~12s wraps often enough for a viewer to notice it.
    long_hits = [h for h in hits if h.get("duration", 0) >= 12]
    for hit in long_hits + [h for h in hits if h not in long_hits]:
        url = _best_file(hit)
        if not url:
            continue
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
        except Exception as e:
            print(f"    download failed ({type(e).__name__}) — next hit")
            continue
        if os.path.getsize(out_path) > 100_000:
            return hit
    return None


def fetch(niche: str, out_path: str | None = None) -> str | None:
    """ONE clip for the whole video. Tries every candidate query before giving up.

    One clip, not one per scene: it runs continuously underneath while the text
    layer cuts, which is what lets assembler.py hard-cut between scenes with no
    crossfade and still look like a single shot.

    Returns None rather than raising when nothing lands — assembler.py falls
    back to a brand gradient, and a flaky stock API is not a reason to lose the
    day's video. It is printed loudly, because a channel quietly running on
    flat gradients for a week is the failure actually worth worrying about.
    """
    if not PIXABAY_API_KEY:
        print("  PIXABAY_API_KEY not set — background will be a flat gradient")
        return None

    out_path = out_path or f"{TEMP_DIR}/bg.mp4"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    for query in _candidates(niche):
        try:
            hits = _search(query)
        except RuntimeError as e:
            # Key-level failure: every remaining query would fail identically.
            print(f"  {e}")
            return None
        if not hits:
            continue
        hit = _download(hits, out_path)
        if hit:
            print(f"  background: {query!r} ({hit.get('duration', '?')}s, "
                  f"id {hit.get('id')})")
            return out_path

    print(f"  every background query failed for niche {niche!r} — "
          f"flat gradient. Check PIXABAY_API_KEY and stock_bg.THEMES.")
    return None
