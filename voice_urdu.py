"""
voice_urdu.py
Urdu narration, with word timings for the karaoke caption.

Lifted from tiktok-reels-agent's voice_generator.py and cut down to one
language. Two engines, and the fallback is the point: Gemini sounds markedly
better but is a preview model on a small per-minute quota, and a day where it
429s must still produce a video. Edge TTS is free, has no quota worth hitting,
and — the reason it is the fallback rather than a second-class path — is the
only one of the two that reports real word boundaries.

When Gemini narrates, the word timings are estimated from word length. That
estimate starts at the first sound, not at t=0: Gemini reliably leaves a beat
of silence before speaking, and measuring it is the difference between a
caption that tracks the voice and one that runs ahead of it all scene.
"""
import asyncio
import base64
import os
import subprocess
import time

import edge_tts
import requests

from config import (
    GEMINI_API_KEY, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE, VOICE_ENGINE,
    EDGE_TTS_UR_VOICE, EDGE_TTS_RATE, GEMINI_MIN_INTERVAL, GEMINI_MAX_BACKOFF,
    TEMP_DIR,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

STYLE = os.environ.get("GEMINI_TTS_STYLE", "").strip() or (
    "Parho ek pur-sukoon, dostana Urdu raavi ki tarah — jaise kisi apne ko "
    "mashwara de rahe ho. Aawaz saaf aur garam, na koi jaldi, na koi "
    "eshtehari lehja, natural pauses ke saath."
)

# Set once when Gemini says the rest of the run is pointless. Without it every
# remaining scene re-runs the same doomed request against the same spent quota.
_gemini_off: str | None = None
_last_call = 0.0


def _quota_verdict(payload: dict) -> tuple[float, str | None]:
    """How long to wait, and whether waiting helps at all.

    A per-minute quota clears on its own. A per-day quota does not clear inside
    a run, so retrying it only spends tomorrow's allowance.
    """
    delay, fatal = 0.0, None
    for detail in (payload.get("error") or {}).get("details") or []:
        kind = detail.get("@type", "")
        if kind.endswith("RetryInfo"):
            try:
                delay = float(str(detail.get("retryDelay", "")).rstrip("s"))
            except ValueError:
                pass
        elif kind.endswith("QuotaFailure"):
            for v in detail.get("violations") or []:
                if "PerDay" in f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}":
                    fatal = f"daily quota exhausted ({v.get('quotaId') or 'PerDay'})"
    return delay, fatal


def _gemini(text: str, out_path: str) -> None:
    global _gemini_off, _last_call
    if _gemini_off:
        raise RuntimeError(f"Gemini TTS off for this run: {_gemini_off}")

    body = {
        "contents": [{"parts": [{"text": f"{STYLE}: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": GEMINI_TTS_VOICE}}},
        },
    }
    last = None
    for attempt in range(1, 3):
        gap = GEMINI_MIN_INTERVAL - (time.monotonic() - _last_call)
        if gap > 0:
            time.sleep(gap)
        _last_call = time.monotonic()
        try:
            r = requests.post(GEMINI_URL.format(model=GEMINI_TTS_MODEL),
                              headers={"x-goog-api-key": GEMINI_API_KEY,
                                       "Content-Type": "application/json"},
                              json=body, timeout=180)
        except Exception as e:
            last = e
            if attempt < 2:
                time.sleep(5)
            continue

        if r.status_code == 429:
            try:
                payload = r.json()
            except ValueError:
                payload = {}
            wait, fatal = _quota_verdict(payload)
            last = RuntimeError(f"HTTP 429: {r.text[:200]}")
            if fatal:
                _gemini_off = fatal
                break
            wait = min(wait or 60.0, GEMINI_MAX_BACKOFF)
            if attempt < 2:
                print(f"  Gemini rate-limited — waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            break

        # A bad key, a wrong model name or a rejected prompt will not come good
        # on a retry, and will not come good on the next scene either.
        if r.status_code in (400, 401, 403, 404):
            _gemini_off = f"HTTP {r.status_code} for {GEMINI_TTS_MODEL}: {r.text[:200]}"
            last = RuntimeError(_gemini_off)
            break
        if r.status_code >= 400:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            if attempt < 2:
                time.sleep(5)
            continue

        try:
            part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            pcm = base64.b64decode(part["data"])
            rate = 24000
            for bit in part.get("mimeType", "").split(";"):
                if bit.strip().startswith("rate="):
                    rate = int(bit.strip()[5:])
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                 "-b:a", "192k", out_path],
                input=pcm, capture_output=True, check=True)
            return
        except Exception as e:
            last = e
            if attempt < 2:
                time.sleep(5)

    raise RuntimeError(f"Gemini TTS failed: {last}")


async def _edge(text: str, out_path: str) -> list[tuple[str, float, float]]:
    comm = edge_tts.Communicate(text, EDGE_TTS_UR_VOICE,
                                rate=EDGE_TTS_RATE, boundary="WordBoundary")
    words = []
    with open(out_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((chunk["text"], start, start + chunk["duration"] / 1e7))
    return words


def _leading_silence(path: str) -> float:
    """Seconds before the narrator's first word, 0.0 if none."""
    try:
        err = subprocess.run(
            ["ffmpeg", "-i", path, "-af", "silencedetect=noise=-40dB:d=0.06",
             "-f", "null", "-"], capture_output=True, text=True).stderr
    except Exception:
        return 0.0
    at_zero = False
    for line in err.splitlines():
        if "silence_start:" in line:
            try:
                at_zero = float(line.split("silence_start:")[1].split()[0]) < 0.05
            except (ValueError, IndexError):
                return 0.0
        elif "silence_end:" in line and at_zero:
            try:
                return max(0.0, float(line.split("silence_end:")[1].split()[0]))
            except (ValueError, IndexError):
                return 0.0
    return 0.0


def duration_of(path: str) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True).stdout.strip())


def narrate(text: str, scene_id: str) -> dict:
    """Return {audio_path, duration, words} for one spoken line."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    out_path = f"{TEMP_DIR}/{scene_id}_voice.mp3"
    text = text.replace("\n", " ").strip()
    words, last_err, engine = [], None, "Edge"

    if VOICE_ENGINE == "gemini" and GEMINI_API_KEY and not _gemini_off:
        try:
            _gemini(text, out_path)
            engine = "Gemini"
        except Exception as e:
            last_err = e
            print(f"  Gemini failed for {scene_id} ({e}) — Edge fallback")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        for _ in range(2):
            try:
                words = asyncio.run(_edge(text, out_path))
                break
            except Exception as e:
                last_err = e

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError(f"No TTS engine produced audio for {scene_id}: {last_err}")

    duration = duration_of(out_path)
    # Say which engine narrated, every time. In the sibling repo success was
    # silent and only failure printed, so the only way to tell whether a video
    # had the good voice was to notice the absence of an error.
    print(f"  {scene_id}: voice via {engine} ({duration:.1f}s)")

    if not words:
        lead = min(_leading_silence(out_path), max(duration - 0.5, 0.0))
        speech = max(duration - lead, 0.1)
        raw = text.split()
        weights = [max(len(w), 2) for w in raw]
        total = sum(weights) or 1
        t = lead
        for w, wt in zip(raw, weights):
            d = speech * wt / total
            words.append((w, t, t + d))
            t += d

    return {"audio_path": out_path, "duration": duration, "words": words}


def available() -> bool:
    return True  # Edge TTS needs no key; there is always a voice.
