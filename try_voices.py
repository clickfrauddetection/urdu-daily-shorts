"""
try_voices.py
Narrate one line in several voices so the channel's voice is picked by ear.

    python try_voices.py                    # the shortlist below
    python try_voices.py Sulafat Charon     # only these
    python try_voices.py --line "..."       # your own Urdu line

Writes out/voice_<name>.mp3 for each. Listen, pick one, and set it as the
GEMINI_TTS_VOICE repo VARIABLE — a variable, not a secret, so the log can say
which voice narrated.

Do NOT rotate voices between videos. A channel's voice is its identity: after
three or four posts a viewer recognises the account by it, and an account that
sounds like a different person every day never builds that. Which voice matters
much less than picking one and staying on it.

Costs a few TTS calls, nothing else. Uses the same ladder as the real run, so
if this prints a model error the real run has the same problem.
"""
import argparse
import os
import sys

import voice_urdu
from config import GEMINI_TTS_MODELS, OUT_DIR

# A shortlist, not the full set — Gemini carries about thirty prebuilt voices
# and comparing thirty is how nobody chooses. These are the ones worth hearing
# for a calm, late-night wellness channel. Names are Gemini's; the character of
# each is a matter of taste, which is the entire reason this script exists
# rather than a recommendation.
SHORTLIST = [
    "Vindemiatrix", "Sulafat", "Achernar", "Callirrhoe", "Aoede",  # softer
    "Charon", "Algenib", "Enceladus",                              # deeper
]

LINE = ("رات کو بستر پر فون دیکھتے ہی نیند کا وقت پیچھے کھسک جاتا ہے۔ "
        "آج رات سونے سے پہلے فون دوسرے کمرے میں رکھ کر دیکھیں۔")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("voices", nargs="*", help="voice names (default: shortlist)")
    ap.add_argument("--line", default=LINE, help="the Urdu line to read")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set — nothing to compare.")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    voices = args.voices or SHORTLIST
    print(f"Model: {GEMINI_TTS_MODELS[0]}")
    print(f"Line:  {args.line[:60]}...\n")

    made = []
    for name in voices:
        out = os.path.join(OUT_DIR, f"voice_{name}.mp3")
        # Set on the module rather than passed in, because the request body is
        # built from config — this is the same code path the real run uses, so
        # what is heard here is what will ship.
        voice_urdu.GEMINI_TTS_VOICE = name
        try:
            voice_urdu._gemini(args.line, out, GEMINI_TTS_MODELS[0], f"try:{name}")
            print(f"  ✅ {name:<14} {out}")
            made.append(name)
        except Exception as e:
            print(f"  ❌ {name:<14} {str(e)[:110]}")

    if made:
        print(f"\nListen to {OUT_DIR}/voice_*.mp3, pick one, then set the repo "
              f"VARIABLE:\n    GEMINI_TTS_VOICE = <name>\nand leave it alone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
