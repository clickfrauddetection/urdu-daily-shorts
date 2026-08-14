"""
main.py
One video, start to finish. Dry run by default.

    python main.py                  # writes an mp4, posts nothing
    python main.py --topic "..."    # skip the queue, script one topic
    python main.py --post           # same, then posts to FB Reels + Shorts

The whole video is laid out on one clock in `plan()` before a frame is
rendered. Picture and voice come out of a single function on purpose: the
sibling repo computed them separately once and the intro ended up playing on
top of the first three step sentences.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import assembler
import content
import guard
import stock_bg
import voice_urdu
from config import (
    NICHE, HOOK_LEAD, SCENE_PAD, MAX_DURATION, TEMP_DIR, OUT_DIR, LOG_FILE,
)
from renderer import render_layer, probe_fonts
from templates.scene import render_scene, FITS

# Between scenes. Much smaller than the opening pad: the background footage is
# continuous across the cut, so a long gap here reads as the video stalling
# rather than as a beat.
SCENE_LEAD = 0.15


def _utf8_console() -> None:
    """Stop a Windows console from killing the run over an Urdu log line.

    The default Windows code page is cp1252, which cannot encode Urdu — so
    printing a topic, or guard.py naming the pattern it matched, raises
    UnicodeEncodeError and takes down a run that was otherwise fine. CI is
    UTF-8 already; this only matters locally, which is where the video is
    actually looked at.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def plan(voices: list[dict]) -> tuple[list[float], list[float], list[float], float]:
    """Return (per-scene lead, per-scene duration, voice start times, total).

    If the script overruns, the pads are squeezed before anything else — they
    are the only slack in the video that costs nothing to lose. A script that
    is still too long after the pads are gone is a writing problem, and it is
    raised as one instead of being silently truncated mid-sentence.
    """
    leads = [HOOK_LEAD] + [SCENE_LEAD] * (len(voices) - 1)
    pads = [SCENE_PAD] * len(voices)
    speech = sum(v["duration"] for v in voices)

    over = speech + sum(leads) + sum(pads) - MAX_DURATION
    if over > 0:
        slack = sum(leads) + sum(pads)
        keep = max(0.0, (slack - over) / slack) if slack else 0.0
        leads = [x * keep for x in leads]
        pads = [x * keep for x in pads]
        print(f"  script runs {over:.1f}s long — pads squeezed to {keep * 100:.0f}%")
    if speech > MAX_DURATION:
        raise ValueError(
            f"The narration alone is {speech:.1f}s, over the {MAX_DURATION:.0f}s "
            f"ceiling. Shorten the script — do not raise the ceiling; a Short "
            f"that runs past 60s loses its Shorts placement.")

    durations, starts, clock = [], [], 0.0
    for lead, pad, v in zip(leads, pads, voices):
        starts.append(clock + lead)
        d = lead + v["duration"] + pad
        durations.append(d)
        clock += d
    return leads, durations, starts, clock


def build(spec: dict, name: str) -> tuple[str, float]:
    scenes = spec["scenes"]

    print("Narrating")
    voices = [voice_urdu.narrate(s["spoken"], f"{name}_s{i}")
              for i, s in enumerate(scenes)]

    leads, durations, starts, total = plan(voices)
    print(f"Building {name}: {len(scenes)} scenes, {total:.1f}s")

    bg = stock_bg.fetch(NICHE)

    print("Rendering layers")
    composed, bg_offset = [], 0.0
    for i, (scene, dur, lead, voice) in enumerate(
            zip(scenes, durations, leads, voices)):
        scene = dict(scene, words=voice["words"])
        html = render_scene(scene, dur, lead, i, len(scenes))
        layer = render_layer(html, f"{name}_s{i}", dur, fits=FITS)
        composed.append(assembler.compose_scene(
            layer, bg, bg_offset, dur, f"{name}_s{i}"))
        bg_offset += dur

    path = assembler.concat(composed, name)
    path = assembler.mux_voice(path, voices, starts, total)
    path = assembler.add_music(path, total)
    print(f"Video written: {path}  ({total:.1f}s)")
    return path, total


def _log(spec: dict, results: dict) -> None:
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    entries = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                pass
    entries.append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "niche": NICHE,
        "topic": spec["topic"],
        "title": spec.get("title", ""),
        "results": results,
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true",
                    help="publish to Facebook Reels and YouTube Shorts")
    ap.add_argument("--topic", help="script this topic instead of the queue's next")
    args = ap.parse_args()
    _utf8_console()

    # Before anything is generated or paid for. A missing Urdu font does not
    # fail the run, it ships a video of empty boxes — success in every log line.
    probe_fonts()
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    topic = args.topic or content.next_topic()
    print(f"Topic: {topic}")
    spec = content.write_script(topic)
    guard.check(spec)

    name = f"{NICHE}_{datetime.now().strftime('%Y%m%d')}"
    # The exact script that produced this file, saved beside it. When a video
    # performs, the only useful question is what was in it.
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    path, total = build(spec, name)

    if not args.post:
        print("\nDRY RUN — nothing was posted. Watch the file above, "
              "then re-run with --post.")
        return 0

    # Imported here so a dry run needs no credentials at all — otherwise the
    # thing being previewed cannot be previewed on a fresh clone.
    results, failures = {}, []
    caption = spec.get("caption", "") + "\n\n" + guard.DISCLAIMER_UR

    try:
        from poster_fb_reels import post_to_fb_reels
        results["facebook"] = post_to_fb_reels(path, caption)
        print("  Facebook Reel published")
    except Exception as e:
        failures.append(f"facebook: {e}")
        print(f"  Facebook failed: {e}")

    try:
        from poster_youtube_shorts import post_to_youtube_shorts
        results["youtube"] = post_to_youtube_shorts(path, spec)
    except Exception as e:
        failures.append(f"youtube: {e}")
        print(f"  YouTube failed: {e}")

    _log(spec, results)

    # Any platform failing fails the job. The sibling repo only fails when ALL
    # platforms fail, and that is exactly what hid a broken poster for a month
    # behind a green tick.
    if failures:
        print("\nFAILED: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
