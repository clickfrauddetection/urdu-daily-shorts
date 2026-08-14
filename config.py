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
NICHE = os.environ.get("NICHE") or "sleep"

# ------------------------------------------------------------------- geometry
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# Render at 2x and let ffmpeg downscale. Urdu — Nastaliq especially — is thin,
# high-contrast type; at 1x the strokes alias and H.264 turns the shimmer into
# blocking. This is the single biggest visible-quality knob in the repo.
SCALE = int(os.environ.get("RENDER_SCALE") or 2)

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
MAX_DURATION = 59.0      # Shorts eligibility; also the attention ceiling

# ---------------------------------------------------------------------- audio
VOICE_TARGET_LUFS = -16
MUSIC_BED_LUFS = -30
DUCK_THRESHOLD = 0.02
DUCK_RATIO = 3
AUDIO_SAMPLE_RATE = 48000

# The TTS ladder, in order. See voice_urdu.py for why this order and not
# another. Every rung is overridable, because a preview model id changes
# without notice and a retired id 404s rather than degrading — which has taken
# the sibling repos down for days at a time.
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL") or "gemini-2.5-flash-preview-tts"
GEMINI_TTS_LITE_MODEL = (os.environ.get("GEMINI_TTS_LITE_MODEL")
                         or "gemini-2.5-flash-lite-preview-tts")
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE") or "Charon"

# Tier 3. OpenAI ships no Urdu voice — this reads Urdu with an English-trained
# voice and the accent is audibly wrong. It is a parachute, not a peer of the
# Gemini tiers.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE") or "onyx"

# Attempts per tier before handing to the next one.
TTS_ATTEMPTS = int(os.environ.get("TTS_ATTEMPTS") or 2)
EDGE_TTS_UR_VOICE = os.environ.get("EDGE_TTS_UR_VOICE") or "ur-PK-AsadNeural"
EDGE_TTS_RATE = os.environ.get("EDGE_TTS_RATE") or "+8%"
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
