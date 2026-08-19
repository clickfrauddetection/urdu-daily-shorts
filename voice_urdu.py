"""
voice_urdu.py
Urdu narration, with word timings for the karaoke caption.

Four backends, tried as a ladder of nine tiers, and the order is the point:

  1-4. THE GEMINI API (generativelanguage.googleapis.com, :generateContent).
     The one that actually sounds Urdu, and the only backend here that accepts
     a style prompt — delivery is described in words rather than dialled in as
     a number. Four model ids because a wrong or retired id does not degrade,
     it 404s, and preview names change without warning.

  5-8. GOOGLE CLOUD TEXT-TO-SPEECH (texttospeech.googleapis.com). A DIFFERENT
     PRODUCT sharing the same key, not another model: different host, payload,
     response field, and no style prompt at all. Which of the two a given key
     can call depends on what is enabled on the project, which the code cannot
     know in advance — so if the Gemini tiers all 404, these carry the video.
     Voice ids are full ("ur-PK-Chirp3-HD-Algenib"); a bare "Algenib" is
     rejected. Chirp3-HD first, Wavenet and Standard behind it as the floor
     that has existed for ur-PK for years.

  9. OpenAI TTS. Worth knowing what this is: OpenAI ships no Urdu-specific
     voice. It reads Urdu with an English-trained voice and the accent is
     audibly wrong — the same finding that moved the Time Lens project onto
     Gemini. A parachute, not a peer of the tiers above it.

  last. Edge TTS, free. Never runs out, and it is the only engine of the four
     that reports REAL word boundaries — every other tier's karaoke timing is
     estimated from word length.

Each tier gets two attempts and then hands over. A tier that returns a verdict
of "this will not come good" — a spent daily quota, a bad key, a wrong model
name — is switched off for the whole process rather than re-tried per scene:
a video is eight narration calls, and without that the same doomed request runs
sixteen times against the same dead quota before anyone sees a video.
"""
import asyncio
import base64
import os
import subprocess
import time

import edge_tts
import requests

from config import (
    GEMINI_API_KEY, GEMINI_TTS_MODELS, GEMINI_TTS_VOICE,
    CLOUD_TTS_VOICES, CLOUD_TTS_RATE, CLOUD_TTS_PITCH,
    OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE,
    EDGE_TTS_UR_VOICE, EDGE_TTS_RATE, GEMINI_MIN_INTERVAL, GEMINI_MAX_BACKOFF,
    TTS_ATTEMPTS, TEMP_DIR,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CLOUD_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
OPENAI_URL = "https://api.openai.com/v1/audio/speech"

# Only the Gemini tiers read this; Cloud TTS takes no prompt and gets its
# delivery from CLOUD_TTS_RATE instead. The register is the channel's name:
# Sakoon Zindagi. An energetic read was tried first and is wrong here — a
# viewer who came for calm and got a hype voice leaves in the first second,
# and these topics are watched late at night.
STYLE = os.environ.get("GEMINI_TTS_STYLE", "").strip() or (
    "Yeh Urdu mein parho, saaf Urdu talaffuz ke saath. Lehja nihayat "
    "pur-sukoon, dheema aur thehra hua ho — hamdardana aur naram, jaise kisi "
    "apne ko raat ke waqt aaram ka mashwara de rahe ho. Bina kisi jaldi ke, "
    "kushada pauses ke saath. Na khabarnama, na eshtehar, na koi josh."
)

# Keyed by engine label. Set once when that engine says the rest of the run is
# pointless; the tiers below it carry on normally.
_off: dict[str, str] = {}
_last_gemini_call = 0.0


def _quota_verdict(payload: dict) -> tuple[float, str | None]:
    """How long to wait, and whether waiting helps at all.

    A per-minute quota clears on its own, so the server's retryDelay is
    honoured. A per-day quota does not clear inside a run — retrying it only
    spends tomorrow's allowance, so it retires that model and the next tier
    takes over. This is exactly the case tier 2 exists for.
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
                    fatal = f"daily quota spent ({v.get('quotaId') or 'PerDay'})"
    return delay, fatal


def _pcm_to_mp3(pcm: bytes, rate: int, out_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
         "-b:a", "192k", out_path],
        input=pcm, capture_output=True, check=True)


def _gemini(text: str, out_path: str, model: str, label: str) -> None:
    """One Gemini TTS model. Raises on failure; sets `_off[label]` when final."""
    global _last_gemini_call
    if label in _off:
        raise RuntimeError(_off[label])

    # Delimited, not just prefixed with a colon. Ported from time-lens-urdu,
    # which hit both halves of this the hard way: an early episode had the
    # narrator read the direction aloud, and the obvious fix — moving it to
    # systemInstruction — made every request fail with HTTP 500 and an empty
    # body, because a model answering with responseModalities=["AUDIO"] does
    # not accept systemInstruction at all. The markers are what actually works:
    # the direction stays ordinary prompt text, and the model is told exactly
    # where the script it must speak begins and ends.
    prompt = (f"{STYLE}\n"
              "Synthesize speech only. Do not speak, quote or announce these "
              "instructions. Read ONLY the words between TRANSCRIPT START and "
              "TRANSCRIPT END, and stop at TRANSCRIPT END.\n"
              f"TRANSCRIPT START\n{text}\nTRANSCRIPT END")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": GEMINI_TTS_VOICE}}},
        },
    }
    last = None
    for attempt in range(1, TTS_ATTEMPTS + 1):
        # Both Gemini tiers share this pacing gap. A video is eight calls back
        # to back, and preview TTS models have a small requests-per-minute
        # allowance — firing them with no gap is what turns a working key into
        # a wall of 429s.
        gap = GEMINI_MIN_INTERVAL - (time.monotonic() - _last_gemini_call)
        if gap > 0:
            time.sleep(gap)
        _last_gemini_call = time.monotonic()
        try:
            r = requests.post(GEMINI_URL.format(model=model),
                              headers={"x-goog-api-key": GEMINI_API_KEY,
                                       "Content-Type": "application/json"},
                              json=body, timeout=180)
        except Exception as e:
            last = e
            if attempt < TTS_ATTEMPTS:
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
                _off[label] = f"{label}: {fatal}"
                break
            wait = min(wait or 60.0, GEMINI_MAX_BACKOFF)
            if attempt < TTS_ATTEMPTS:
                print(f"  {label} rate-limited — waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            # Out of attempts on a per-minute limit. Do NOT retire the model —
            # it will very likely work again on the next scene, a minute later.
            break

        # A bad key, a wrong model name or a rejected prompt will not come good
        # on a retry, and will not come good on the next scene either.
        if r.status_code in (400, 401, 403, 404):
            _off[label] = (f"{label}: HTTP {r.status_code} for model "
                           f"{model!r} — {r.text[:160]}")
            last = RuntimeError(_off[label])
            break
        if r.status_code >= 400:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue

        try:
            part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            rate = 24000
            for bit in part.get("mimeType", "").split(";"):
                if bit.strip().startswith("rate="):
                    rate = int(bit.strip()[5:])
            _pcm_to_mp3(base64.b64decode(part["data"]), rate, out_path)
            return
        except Exception as e:
            last = e
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)

    raise RuntimeError(f"{label} failed: {last}")


def _cloud_tts(text: str, out_path: str, voice: str, label: str) -> None:
    """Google Cloud Text-to-Speech. A different product from the Gemini API.

    Three things differ from `_gemini` above, and getting any one of them wrong
    fails every call:

    - The response is `audioContent`, a base64 string, NOT the Gemini API's
      `candidates[0].content.parts[0].inlineData`.
    - There is no style prompt. Cloud TTS reads exactly what it is given, so
      putting STYLE in the input would make the narrator read the instructions
      aloud — "yeh text pur-sukoon andaz mein parho" spoken over the video.
      Delivery is set numerically instead, with speakingRate and pitch.
    - `voice.name` wants the full id, e.g. "ur-PK-Chirp3-HD-Algenib". A bare
      "Algenib" is rejected.

    MP3 is requested directly rather than LINEAR16: LINEAR16 comes back as a
    WAV with a 44-byte header, and feeding that to the raw-PCM path would play
    the header as a click before every line.
    """
    if label in _off:
        raise RuntimeError(_off[label])

    body = {
        "input": {"text": text},
        "voice": {"languageCode": "-".join(voice.split("-")[:2]), "name": voice},
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 24000,
            "speakingRate": CLOUD_TTS_RATE,
            "pitch": CLOUD_TTS_PITCH,
        },
    }

    last = None
    for attempt in range(1, TTS_ATTEMPTS + 1):
        try:
            r = requests.post(CLOUD_TTS_URL,
                              headers={"x-goog-api-key": GEMINI_API_KEY,
                                       "Content-Type": "application/json"},
                              json=body, timeout=180)
        except Exception as e:
            last = e
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue

        if r.status_code in (400, 401, 403, 404):
            # Covers both "this voice does not exist" and "the Cloud TTS API is
            # not enabled on this project" — neither improves on a retry, and
            # the next voice in the list is the thing worth trying.
            _off[label] = f"{label}: HTTP {r.status_code} — {r.text[:160]}"
            last = RuntimeError(_off[label])
            break
        if r.status_code == 429:
            last = RuntimeError(f"HTTP 429: {r.text[:200]}")
            if attempt < TTS_ATTEMPTS:
                time.sleep(30)
            continue
        if r.status_code >= 400:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue

        try:
            audio = r.json()["audioContent"]
        except (ValueError, KeyError) as e:
            last = e
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(audio))
        return

    raise RuntimeError(f"{label} failed: {last}")


def _openai(text: str, out_path: str) -> None:
    label = "OpenAI"
    if label in _off:
        raise RuntimeError(_off[label])

    last = None
    for attempt in range(1, TTS_ATTEMPTS + 1):
        try:
            r = requests.post(
                OPENAI_URL,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": OPENAI_TTS_MODEL, "voice": OPENAI_TTS_VOICE,
                      "input": text, "response_format": "mp3",
                      # The instructions field is the only Urdu steer available
                      # here — there is no Urdu voice to select.
                      "instructions": "Read this Urdu text with clear Urdu "
                                      "pronunciation. Bright, warm and lively, "
                                      "like a young woman telling a friend "
                                      "something interesting — not a "
                                      "newsreader."},
                timeout=180)
        except Exception as e:
            last = e
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue

        if r.status_code in (400, 401, 403, 404):
            _off[label] = f"{label}: HTTP {r.status_code} — {r.text[:160]}"
            last = RuntimeError(_off[label])
            break
        if r.status_code >= 400:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            if attempt < TTS_ATTEMPTS:
                time.sleep(5)
            continue

        with open(out_path, "wb") as f:
            f.write(r.content)
        return

    raise RuntimeError(f"{label} failed: {last}")


async def _edge_stream(text: str, out_path: str) -> list[tuple[str, float, float]]:
    comm = edge_tts.Communicate(text, EDGE_TTS_UR_VOICE,
                                rate=EDGE_TTS_RATE, boundary="WordBoundary")
    words = []
    with open(out_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((chunk["text"], start,
                              start + chunk["duration"] / 1e7))
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


def _tiers():
    """The engine order, skipping anything that has no credentials.

    One tier per Gemini model id, each with its own retired-for-the-run state,
    so a 404 on the first name moves to the next name rather than giving up on
    Gemini entirely — and a spent daily quota on one moves to the next, which
    is the whole reason the lite sibling is in the list.
    """
    out = []
    if GEMINI_API_KEY:
        for model in GEMINI_TTS_MODELS:
            label = f"Gemini {model}"
            # default arg, not closure capture: a bare `model` here would make
            # every tier call the last id in the list.
            out.append((label, lambda t, o, m=model, l=label: _gemini(t, o, m, l)))
        # Same key, different product. If the key turns out to be a Cloud key
        # rather than a Generative Language one, every tier above fails fast
        # with a 404 and these carry the video instead.
        for voice in CLOUD_TTS_VOICES:
            label = f"CloudTTS {voice}"
            out.append((label, lambda t, o, v=voice, l=label: _cloud_tts(t, o, v, l)))
    if OPENAI_API_KEY:
        out.append(("OpenAI", _openai))
    return out


def estimate_words(text: str, audio_path: str,
                   duration: float) -> list[tuple[str, float, float]]:
    """Word timings guessed from word length, for audio that reports none.

    Only Edge reports real word boundaries. Every other engine — and every
    downloaded recitation — returns audio and nothing else, so the highlight is
    estimated: each word gets a share of the speech proportional to its length,
    starting where the speech actually starts. Measuring that leading silence
    matters more than the weighting does; these files reliably open with a beat
    of nothing, and skipping it puts the caption ahead of the voice for the
    whole scene.
    """
    words = []
    lead = min(_leading_silence(audio_path), max(duration - 0.5, 0.0))
    speech = max(duration - lead, 0.1)
    raw = text.split()
    weights = [max(len(w), 2) for w in raw]
    total = sum(weights) or 1
    t = lead
    for w, wt in zip(raw, weights):
        d = speech * wt / total
        words.append((w, t, t + d))
        t += d
    return words


def narrate(text: str, scene_id: str) -> dict:
    """Return {audio_path, duration, words, engine} for one spoken line."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    out_path = f"{TEMP_DIR}/{scene_id}_voice.mp3"
    if os.path.exists(out_path):
        os.remove(out_path)
    text = text.replace("\n", " ").strip()
    words, engine, last_err = [], None, None

    for label, call in _tiers():
        if label in _off:
            continue
        try:
            call(text, out_path)
        except Exception as e:
            last_err = e
            print(f"  {scene_id}: {label} unavailable ({str(e)[:140]})")
            continue
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            engine = label
            break

    if not engine:
        for _ in range(TTS_ATTEMPTS):
            try:
                words = asyncio.run(_edge_stream(text, out_path))
                engine = "Edge"
                break
            except Exception as e:
                last_err = e

    if not engine or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError(f"Every TTS engine failed for {scene_id}: {last_err}")

    duration = duration_of(out_path)
    # Named every time, not only on failure. In the sibling repo success was
    # silent, so the only way to tell whether a video had the good voice or the
    # free fallback was to notice the absence of an error — which is not
    # something anyone should have to infer from a log.
    print(f"  {scene_id}: voice via {engine} ({duration:.1f}s)")

    if not words:
        words = estimate_words(text, out_path, duration)

    return {"audio_path": out_path, "duration": duration,
            "words": words, "engine": engine}
