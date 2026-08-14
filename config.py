"""
config.py
One place for every knob. Credentials come from the environment only — the
same secret VALUES as social-media-posts-agent and tiktok-reels-agent, so a
new Meta app / YouTube client is not needed, only new repo secrets.
"""
import os

# ---------------------------------------------------------------- credentials
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

# Only ever used as the background fallback when Pixabay comes back with
# nothing — see replicate_bg.py. "still" generates one FLUX image and lets the
# compositor's drift animate it (~$0.003); "motion" adds an LTX-Video clip on
# top (~$0.057, and the sibling repo turned it off because the clips came back
# uneven). Nothing here runs on a normal day.
REPLICATE_API_KEY = os.environ.get("REPLICATE_API_TOKEN", "")
REPLICATE_BG_MODE = (os.environ.get("REPLICATE_BG_MODE") or "still").lower()

# Replicate hangs for minutes under provider load often enough to need a hard
# wall-clock bound per attempt, not just a request timeout.
IMAGE_GEN_TIMEOUT = int(os.environ.get("IMAGE_GEN_TIMEOUT") or 60)
MOTION_GEN_TIMEOUT = int(os.environ.get("MOTION_GEN_TIMEOUT") or 180)
IMAGE_GEN_RETRIES = int(os.environ.get("IMAGE_GEN_RETRIES") or 3)

FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_API_VERSION = "v21.0"

YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# One constant for the model id, per the sibling repos. A retired id 404s
# rather than degrading, and it has taken those repos down for days at a time.
DEFAULT_CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"

# ---------------------------------------------------------------------- niche
# The whole channel's subject, in one place. Everything downstream — topics,
# the writing prompt, the safety guard, the hashtags — reads from here, so a
# second channel is a second profile, not a second repo.
# The channel is "Sakoon Zindagi" — health, sleep and peaceful living.
NICHE = os.environ.get("NICHE") or "daily"

# ------------------------------------------------------------------- geometry
WIDTH, HEIGHT = 1080, 1920
# 25, not 30. Every platform accepts 23-60, and the renderer's cost is per
# frame — this is 17% of the whole build for something no viewer can see.
FPS = int(os.environ.get("FPS") or 25)

# 1, after measuring. The theory for 2x was sound — Nastaliq is thin,
# high-contrast type and downscaling from 2x with lanczos gives cleaner edges —
# but the frames were compared side by side at 1080 and the difference is not
# visible, while the cost is: a 7-second scene took 220s at 2x and 46s at 1x,
# which is 29 minutes of rendering for one video versus 6. That was the whole
# reason the first CI run sat there for 16 minutes with nothing to show.
# RENDER_SCALE=2 is still there for a one-off video worth the wait.
SCALE = int(os.environ.get("RENDER_SCALE") or 1)

# Platform UI safe zones, in 1080x1920 space. Facebook Reels and YouTube
# Shorts both draw over the video: the caption/profile bar along the bottom,
# the like/comment/share column down the right, the sound strip at the top.
# Text outside this box gets covered on one platform or the other.
SAFE_TOP = 190
SAFE_BOTTOM = 340
SAFE_RIGHT = 150
SAFE_LEFT = 70

# --------------------------------------------------------------------- timing
HOOK_LEAD = 0.6          # frame lands before the first word
SCENE_PAD = 0.35         # breath after a scene's last word
XFADE = 0.25             # crossfade between scenes
MAX_DURATION = 59.0      # the target: Shorts placement, and the attention ceiling
# The point past which the video is genuinely not publishable. Between
# MAX_DURATION and this, the script is re-asked once and then shipped long —
# losing the day's video over four seconds is a worse trade than posting a
# 64-second Short. FB Reels allows 90s and YouTube Shorts now allows well past
# a minute, so overrunning costs placement, not the post.
HARD_MAX_DURATION = float(os.environ.get("HARD_MAX_DURATION") or 80.0)

# ---------------------------------------------------------------------- audio
VOICE_TARGET_LUFS = -16
# -26, up from -30. Four dB is a clearly audible lift and the bed now reads as
# part of the video rather than as something left on by accident. It is still
# ~10 LU under the voice, which is inside the usual broadcast voice-over gap —
# going much past this starts costing intelligibility on a phone speaker.
MUSIC_BED_LUFS = float(os.environ.get("MUSIC_BED_LUFS") or -26)
DUCK_THRESHOLD = 0.02
DUCK_RATIO = 3
AUDIO_SAMPLE_RATE = 48000

# The TTS ladder, in order. See voice_urdu.py for why this order and not
# another. Every rung is overridable, because a preview model id changes
# without notice and a retired id 404s rather than degrading — which has taken
# the sibling repos down for days at a time.
# The model list lives in CODE, not in a secret. A secret holds the API key;
# which model to call is a code decision, and putting it in a secret means the
# one value nobody can read back is also the one most likely to be wrong.
#
# A list rather than one id, tried in order, because a wrong or retired id does
# not degrade — it 404s outright, which is what silently switched Gemini off
# for the whole of run #2. They are also separate quota buckets: the quota is
# named GenerateRequestsPerDayPerProjectPerModel, per model, so a spent daily
# cap on the first costs the video nothing.
#
# This order is from THIS repo's own live runs, not from another repo's notes.
# Both matter, and they disagreed:
#
#   gemini-3.1-flash-tts-preview       WORKS on this key — narrated all eight
#                                      scenes of the 2026-08-14 run. It is
#                                      first because it is the only model here
#                                      actually observed producing audio.
#   gemini-3.1-flash-lite-tts-preview  404, observed. Removed, not demoted.
#   gemini-2.5-*                       unproven here; behind the working one.
#
# time-lens-urdu's chain excludes 3.1 with a note saying it answers HTTP 500 on
# every request, and I moved this repo to 2.5 on the strength of that — which
# was wrong, because 3.1 was already narrating here. A model id that fails on
# one project can be fine on another: enablement and allowlisting are per
# project. A log from the account in question outranks a comment from a repo
# that runs on a different one.
#
# They are also separate daily quota buckets — the quota is literally named
# GenerateRequestsPerDayPerProjectPerModel — so the ones behind the leader are
# not decoration; they are what a spent cap falls through to.
GEMINI_TTS_MODELS = [
    m.strip() for m in (os.environ.get("GEMINI_TTS_MODELS") or
                        "gemini-3.1-flash-tts-preview,"
                        "gemini-2.5-flash-preview-tts,"
                        "gemini-2.5-flash-lite-preview-tts").split(",")
    if m.strip()
]

# Google Cloud Text-to-Speech is a DIFFERENT PRODUCT from the Gemini API, not
# another model on it: different host, different payload, different response
# field, and no style prompt at all. Which one a GEMINI_API_KEY can actually
# call depends on what is enabled on the project, and that is not something the
# code can know in advance — so both are tried, Gemini first, and whichever
# answers is the one that narrates.
#
# Voice ids here are FULL ids on purpose. Cloud TTS rejects a bare "Algenib":
# the name field wants "ur-PK-Chirp3-HD-Algenib". Chirp3-HD is the good one and
# may not be enabled everywhere, so Wavenet and Standard sit behind it — those
# have existed for ur-PK for years and are the floor that always answers.
CLOUD_TTS_VOICES = [
    v.strip() for v in (os.environ.get("CLOUD_TTS_VOICES") or
                        "ur-PK-Chirp3-HD-Algenib,"
                        "ur-PK-Chirp3-HD-Charon,"
                        "ur-PK-Wavenet-A,"
                        "ur-PK-Standard-A").split(",")
    if v.strip()
]
# Cloud TTS takes no prompt, so delivery is set numerically or not at all.
# Slightly under 1.0 is the whole "sakoon" register in one number.
CLOUD_TTS_RATE = float(os.environ.get("CLOUD_TTS_RATE") or 0.94)
CLOUD_TTS_PITCH = float(os.environ.get("CLOUD_TTS_PITCH") or 0.0)
# Calm and settled, matching the channel's name. Chosen over a bright, quick
# read: these topics are watched late at night, and someone who came for
# sakoon and got a hype voice is gone in the first second. Algenib is soft and
# clear; Charon is deeper if a heavier read is wanted.
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE") or "Algenib"

# Tier 3. OpenAI ships no Urdu voice — this reads Urdu with an English-trained
# voice and the accent is audibly wrong. It is a parachute, not a peer of the
# Gemini tiers.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
# Warm and unhurried rather than bright. Same register decision as the
# Gemini voice above.
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE") or "shimmer"

# Attempts per tier before handing to the next one.
TTS_ATTEMPTS = int(os.environ.get("TTS_ATTEMPTS") or 2)
EDGE_TTS_UR_VOICE = os.environ.get("EDGE_TTS_UR_VOICE") or "ur-PK-UzmaNeural"
# Below zero on purpose: Edge is the free floor and reads fast by default,
# which is the opposite of this channel.
EDGE_TTS_RATE = os.environ.get("EDGE_TTS_RATE") or "-6%"
GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_TTS_MIN_INTERVAL") or 6)
GEMINI_MAX_BACKOFF = float(os.environ.get("GEMINI_TTS_MAX_BACKOFF") or 75)

# --------------------------------------------------------------------- colour
PALETTE = {
    "ink": "#F7FAFC",
    # Deliberately dim. This is the colour of a word that has NOT been spoken
    # yet, and at #B8C4D0 the highlight was invisible on a phone — the karaoke
    # line just looked like a static subtitle.
    "muted": "#6C7A8C",
    "accent": "#FFC93C",
    "accent_2": "#4ADE80",
    "scrim": "rgba(6,10,18,.62)",
}

# ----------------------------------------------------------------------- dirs
TEMP_DIR = "temp"
OUT_DIR = "out"
DATA_DIR = "data"
FONT_DIR = "fonts"
MUSIC_DIR = "data/music"
LOG_FILE = "data/posted_log.json"
TOPICS_FILE = "data/topics.json"
