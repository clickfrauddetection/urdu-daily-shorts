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
import json
import os
import random
import subprocess
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
    "ghar": ["sunlight through curtains", "calm bedroom window",
             "plant leaves sunlight", "kitchen window morning"],
    "aadat": ["park path morning", "running shoes road", "water pouring glass",
              "mountain trail sunrise", "ocean waves slow"],
    "rishtay": ["sunset field warm", "tea cup steam", "park bench evening",
                "warm light window"],
    "warzish": ["park path morning", "running shoes road", "stairs sunlight",
                "mountain trail sunrise", "empty street dawn"],
    "khurak": ["water pouring glass", "kitchen window morning",
               "fruit table light", "tea cup steam", "market vegetables"],
    "usool": ["desk sunlight morning", "book pages turning", "sand timer",
              "calm room window", "notebook pen desk"],
    # The scripture days. Naseem's call, and it is the right one for an Urdu
    # audience: green mountain country — Fairy Meadows, streams, alpine
    # valleys — rather than the desert-and-starfield look every Islamic page on
    # the internet already uses. It is also the scenery this audience lives
    # under, which is worth more than a stock idea of the Middle East.
    #
    # Nothing figurative and nobody in frame: a stock clip of a stranger
    # praying under an ayah attaches a face to revelation, and it is the exact
    # look that reads as content-farm output.
    "quran": ["green meadow mountains", "mountain stream forest",
              "alpine valley green", "pine forest mist", "waterfall forest",
              "snow peaks clouds"],
    "hadith": ["river valley mountains", "grass meadow wind",
               "forest light rays", "mountain lake calm",
               "green hills clouds", "stream rocks water"],
    # The ibrat story. A road, a doorway, a long evening shadow — the look of
    # a moment a person is standing in and about to choose from. Deliberately
    # not the scripture greenery: those videos ARE the verse, this one is a
    # story that ends on one, and opening them on the same picture would make
    # the two kinds look like one repeated post.
    #
    # Nothing figurative and nobody in frame, for the same reason as the
    # scripture themes: a stock stranger's face on a story about a wrong turn
    # attaches that wrong turn to a real person.
    "ibrat": ["empty road horizon", "long shadows evening", "open door light",
              "footprints sand", "dusk street lamp", "clouds timelapse"],
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


# Mean luma, 0-255, under which a clip is treated as night footage. A normally
# exposed daylight frame sits near 110-140; the dusk forest that carried the
# channel's only engaging video measured 46 on the hook frame and 32 on the
# ayah, AFTER the scrim — so the source was already dim before anything was
# laid over it.
#
# 90 is a floor rather than a target: it drops night and heavy-dusk clips and
# keeps everything an overcast afternoon produces. Raise it for brighter
# footage, at the cost of a smaller pool to shuffle.
MIN_BRIGHTNESS = float(os.environ.get("BG_MIN_BRIGHTNESS") or 90)


def _thumb_url(hit: dict) -> str | None:
    videos = hit.get("videos", {})
    for size in ("medium", "small", "large", "tiny"):
        url = videos.get(size, {}).get("thumbnail")
        if url:
            return url
    return None


def _brightness(hit: dict) -> float | None:
    """Mean luma of a hit's thumbnail, or None if it cannot be measured.

    The thumbnail rather than the clip: a few kilobytes against tens of
    megabytes, and for "is this footage shot at night" it is the same answer.
    ffmpeg does the decoding because it is already a hard dependency here and
    an image library is not.
    """
    url = _thumb_url(hit)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0",
             "-vf", "scale=32:32", "-pix_fmt", "gray",
             "-f", "rawvideo", "pipe:1"],
            input=r.content, capture_output=True, timeout=30)
    except Exception:
        return None
    data = proc.stdout[:32 * 32]
    if proc.returncode or not data:
        return None
    return sum(data) / len(data)


# How many bright hits are enough to stop looking. The pool exists to be
# shuffled, and a dozen candidates shuffle as well as thirty — while thirty
# measurements is thirty HTTP requests and thirty ffmpeg processes, per query,
# on every run.
ENOUGH_BRIGHT = int(os.environ.get("BG_ENOUGH_BRIGHT") or 8)


def _daylight(hits: list[dict]) -> list[dict]:
    """The hits bright enough to read type over, or the best that is left.

    Measures lazily: it stops as soon as it has ENOUGH_BRIGHT, because Pixabay
    returns thirty hits and measuring all of them costs a minute of wall clock
    to choose one background.

    Never returns empty from a non-empty input. Losing the background entirely
    because every candidate was dim is a worse outcome than a dim background.
    """
    if not hits:
        return hits

    lit, dark, unknown = [], [], []
    seen = 0
    for h in hits:
        if len(lit) >= ENOUGH_BRIGHT:
            break
        seen += 1
        b = _brightness(h)
        if b is None:
            unknown.append(h)
        elif b >= MIN_BRIGHTNESS:
            lit.append(h)
        else:
            dark.append(h)

    rest = hits[seen:]
    print(f"    brightness: {len(lit)} bright, {len(dark)} too dark, "
          f"{len(unknown)} unmeasured, {len(rest)} not looked at "
          f"(floor {MIN_BRIGHTNESS:g})")

    # Order of preference, and it matters. An unmeasured hit is NOT as good as
    # one known to be bright — letting the two share a pool means a thumbnail
    # Pixabay was slow to serve can win the shuffle over a clip that was
    # actually checked. So: the bright ones alone if there are any, then the
    # ones nothing is known about, and only then the ones known to be dark.
    return lit or (unknown + rest) or dark


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


USED_FILE = "data/bg_used.json"
# How many clips to remember. Thirty days of one video a day is enough that a
# viewer scrolling the page cannot see the same footage twice, and small enough
# that the list never starves a query of candidates.
USED_MEMORY = int(os.environ.get("BG_MEMORY") or 60)


def _used() -> list[int]:
    if not os.path.exists(USED_FILE):
        return []
    try:
        with open(USED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def remember(hit_id: int) -> None:
    """Record a clip as used, so the next few weeks do not reuse it."""
    ids = [i for i in _used() if i != hit_id][-(USED_MEMORY - 1):] + [hit_id]
    os.makedirs(os.path.dirname(USED_FILE) or ".", exist_ok=True)
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f)


def _download(hits: list[dict], out_path: str) -> dict | None:
    """A hit that actually downloads — random among the good ones, not the first.

    Two things were wrong with taking the first. The query list is shuffled per
    run, so the SUBJECT varied — but Pixabay's ordering for a given query does
    not, so a niche with six themes was really a rotation of six clips, and
    after a fortnight the page is visibly the same handful of videos. And a
    channel whose footage repeats is not only dull; repetitive output is what
    both platforms' inauthentic-content rules are written about.

    So: shuffle, and skip anything used in the last USED_MEMORY videos.
    """
    # Long enough that the loop point is not obvious inside a 60-second video.
    # Anything under ~12s wraps often enough for a viewer to notice it.
    # Dropped before anything else, so the shuffle below still shuffles — the
    # brightest hit is not simply chosen every time, which would put one clip
    # behind every video that ever used this query.
    hits = _daylight(hits)

    long_hits = [h for h in hits if h.get("duration", 0) >= 12]
    short_hits = [h for h in hits if h.get("duration", 0) < 12]
    random.shuffle(long_hits)
    random.shuffle(short_hits)

    seen = set(_used())
    fresh = [h for h in long_hits if h.get("id") not in seen]
    stale = [h for h in long_hits if h.get("id") in seen]
    # Used clips are the last resort, not a refusal: a channel that would
    # rather have no background than a repeated one has its priorities the
    # wrong way round.
    for hit in fresh + short_hits + stale:
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
            if hit.get("id"):
                remember(hit["id"])
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
