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
import time
from datetime import datetime, timezone

import assembler
import config
import content
import guard
import replicate_bg
import stock_bg
import voice_urdu
from config import (
    NICHE, CHANNEL_NAME, HOOK_LEAD, SCENE_PAD, MAX_DURATION, HARD_MAX_DURATION,
    TEMP_DIR, OUT_DIR, LOG_FILE, CONTENT_KIND, RECITATION_PAD,
)
from renderer import render_layer, probe_fonts

# Both writers, both guards, both frames — loaded, not chosen, because the
# choice is made per RUN rather than per repo. See _kind_for_today().
import content_islamic
import content_text
import guard_islamic
import islamic_sources
from templates import scene as scene_habit
from templates import scene_islamic as scene_scripture
from templates import scene_text

# What a scripture day looks like next to a habit day. Everything that differs
# between the two kinds of video is in this table and nowhere else, which is
# the only reason one channel can alternate without two of every function.
KINDS = {
    "habit": {
        "writer": content,
        "guard": guard,
        "render_scene": scene_habit.render_scene,
        "fits_for": lambda _scene: scene_habit.FITS,
        "music": "bed",
    },
    "scripture": {
        "writer": content_islamic,
        "guard": guard_islamic,
        "render_scene": scene_scripture.render_scene,
        "fits_for": scene_scripture.fits_for,
        # Never "bed". See assembler's policy note: nothing melodic goes under
        # a recitation, and the recitation's own window is silenced outright.
        "music": "ambient",
    },
    "text": {
        # No narrator at all — see content_text.py. The music is the only
        # audio, so it is a bed rather than ambience: with nothing over it,
        # ambience is indistinguishable from a video whose sound is broken.
        "writer": content_text,
        "guard": guard,
        "render_scene": scene_text.render_scene,
        "fits_for": scene_text.fits_for,
        "music": "bed",
    },
}

# What an ayah frame is worth on its own when the recitation could not be
# downloaded. Long enough to read it, short enough that a viewer does not think
# the video has frozen.
SILENT_AYAH_SECONDS = float(os.environ.get("SILENT_AYAH_SECONDS") or 4.5)

# The hook holds in silence so the first SOUND of the video is the recitation.
# Two seconds is what a scroll takes to decide, and it is also about as long as
# six words of Nastaliq need to be read — any longer and the video has a gap in
# it before it has earned one.
SILENT_HOOK_SECONDS = float(os.environ.get("SILENT_HOOK_SECONDS") or 2.2)


def _published() -> int:
    """How many videos this channel has actually posted.

    The same count drives three things — which pillar the habit queue is on,
    which entries the scripture queue has used, and whose turn it is today —
    and it counts POSTS, not runs. A day the build fails, or a rehearsal that
    published nowhere, does not flip the rhythm.
    """
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError:
            return 0
    return len([e for e in entries if e.get("results")])


def _kind_for_today(override: str | None = None) -> str:
    """Which of the two daily slots this run is standing in for.

    Only reached on a manual run that chose nothing: the schedule picks by the
    clock, in the workflow. It alternates scripture and text because those are
    the two kinds actually on the calendar — habit is still in KINDS and still
    buildable by name, it is simply no longer part of the rotation.
    """
    if override:
        return override
    if CONTENT_KIND in KINDS:
        return CONTENT_KIND
    return "scripture" if _published() % 2 else "text"


_T0 = time.monotonic()


def step(msg: str) -> None:
    """A log line with the elapsed time on it.

    Sixteen minutes of silence is indistinguishable from a hang, and that is
    how the first CI run read — the build was working the whole time, there
    was simply nothing to say so. Every phase announces itself with a running
    clock now, and flush=True because CI captures a pipe, not a terminal, so
    Python buffers stdout and holds it all until the process exits.
    """
    print(f"[{time.monotonic() - _T0:6.1f}s] {msg}", flush=True)

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
    if speech > HARD_MAX_DURATION:
        raise ValueError(
            f"The narration alone is {speech:.1f}s, past the "
            f"{HARD_MAX_DURATION:.0f}s point where this stops being a short. "
            f"The re-ask did not shorten it — check the script in out/.")

    durations, starts, clock = [], [], 0.0
    for lead, pad, v in zip(leads, pads, voices):
        starts.append(clock + lead)
        d = lead + v["duration"] + pad
        durations.append(d)
        clock += d
    return leads, durations, starts, clock


def _narrate_all(scenes: list[dict], name: str, tag: str = "",
                 source: dict | None = None) -> list[dict]:
    """One audio clip per scene — narrated, recited, or deliberately silent.

    A scene marked `recite` is not narrated at all. Its audio is the qari's
    recitation of that exact ayah, downloaded from the same source the text
    came from. A synthetic Urdu voice reading Arabic would be the wrong thing
    in a way no amount of production polish would cover, so when the download
    fails the scene holds in silence instead — the ayah is on screen and it can
    be read.

    `recite_ur` is the same idea one step further: the recorded reading of the
    translation, by a person, so that nothing in the scripture block is
    synthetic. That one DOES fall back to the narrator — a translation read in
    the channel's own voice is a fine video, it is only the second-best one.
    """
    out = []
    for i, scene in enumerate(scenes):
        if scene.get("recite"):
            path = os.path.join(TEMP_DIR, f"{name}{tag}_recite.mp3")
            clip = islamic_sources.recitation(source or {}, path)
            if clip:
                secs = voice_urdu.duration_of(clip)
                step(f"  recitation: {secs:.1f}s from {source.get('source')}")
                out.append({"audio_path": clip, "duration": secs,
                            "words": [], "engine": "recitation"})
            else:
                step("  recitation unavailable — holding the ayah in silence")
                out.append({"audio_path": None, "duration": SILENT_AYAH_SECONDS,
                            "words": [], "engine": "silent"})
            continue
        if scene.get("recite_ur"):
            path = os.path.join(TEMP_DIR, f"{name}{tag}_tarjuma.mp3")
            clip = islamic_sources.recitation(source or {}, path,
                                              "urdu_audio_url")
            if clip:
                secs = voice_urdu.duration_of(clip)
                step(f"  translation read by {config.QURAN_UR_RECITER} "
                     f"({secs:.1f}s)")
                out.append({
                    "audio_path": clip, "duration": secs, "engine": "human",
                    # No word boundaries come with a downloaded file, so the
                    # karaoke line is estimated the same way it is for every
                    # TTS engine except Edge.
                    "words": voice_urdu.estimate_words(
                        scene["spoken"], clip, secs)})
                continue
            step("  recorded translation unavailable — the narrator reads it")

        if not (scene.get("spoken") or "").strip():
            # A scene can name its own hold. The silent text card is one
            # unbroken scroll whose length comes from how much there is to
            # read, not from a constant that was chosen for an ayah frame.
            held = scene.get("hold") or (
                SILENT_HOOK_SECONDS if scene["role"] == "hook"
                else SILENT_AYAH_SECONDS)
            out.append({"audio_path": None, "duration": held,
                        "words": [], "engine": "silent"})
            continue
        out.append(voice_urdu.narrate(scene["spoken"], f"{name}{tag}_s{i}"))
    return out


def build(spec: dict, name: str, pillar: str, kind: str) -> tuple[str, float]:
    plan_of = KINDS[kind]
    scenes = spec["scenes"]
    source = spec.get("source")

    step(f"Narrating {len(scenes)} lines")
    voices = _narrate_all(scenes, name, source=source)

    # The word budget in the prompt is an estimate; the clock is the truth, and
    # only the narrator knows it. Rather than failing — which is what run #2
    # did, after paying for a script and eight TTS calls — measure the overrun
    # and ask for a script that fits, with the real number in hand. One retry:
    # a second is more likely to be the model being stubborn than to help.
    speech = sum(v["duration"] for v in voices)
    if speech > MAX_DURATION and kind == "scripture":
        # No re-ask here. The overrun in a scripture video is the recitation
        # and the translation, and neither is the model's to shorten — asking
        # for fewer words would only cut the explanation, which is the part
        # that was already short. A long verse is a QUEUE decision: swap it in
        # data/islamic_queue.json for a shorter one.
        step(f"Narration is {speech:.1f}s, over {MAX_DURATION:.0f}s — the "
             f"verse and its translation set this length. Shipping it long; "
             f"pick a shorter entry if this happens often.")
    elif speech > MAX_DURATION:
        words = sum(len(s["spoken"].split()) for s in scenes)
        target = max(int(words * (MAX_DURATION - 5) / speech), 60)
        step(f"Narration is {speech:.1f}s, over {MAX_DURATION:.0f}s — "
             f"re-asking for {target} words instead of {words}")
        try:
            spec["scenes"] = scenes = content.write_script(
                spec["topic"], pillar, max_words=target)["scenes"]
            plan_of["guard"].check(spec)
            voices = _narrate_all(scenes, name, "_r", source=source)
            step(f"Re-ask narrates in {sum(v['duration'] for v in voices):.1f}s")
        except Exception as e:
            # A failed re-ask is not worth the day's video either. Ship the
            # long one; plan() still refuses only what is past publishable.
            step(f"Re-ask failed ({e}) — building the long cut")

    leads, durations, starts, total = plan(voices)
    step(f"Planned {total:.1f}s over {len(scenes)} scenes")

    # Real footage first; generate one only when there is none. Stock is free,
    # and a real clip of a real room still beats a generated one at holding a
    # viewer — the generated path is the parachute, not the plan.
    step("Fetching the background")
    bg = stock_bg.fetch(pillar) or replicate_bg.fetch(pillar)

    step("Rendering scene layers")
    composed, bg_offset = [], 0.0
    for i, (scene, dur, lead, voice) in enumerate(
            zip(scenes, durations, leads, voices)):
        scene = dict(scene, words=voice["words"])
        html = plan_of["render_scene"](scene, dur, lead, i, len(scenes))
        layer = render_layer(html, f"{name}_s{i}", dur,
                             fits=plan_of["fits_for"](scene))
        composed.append(assembler.compose_scene(
            layer, bg, bg_offset, dur, f"{name}_s{i}", index=i))
        bg_offset += dur

    # Where the bed must not play at all. Ducking is a level decision and this
    # is not one — see assembler.add_music.
    quiet = [(starts[i] - RECITATION_PAD, starts[i] + voices[i]["duration"])
             for i, s in enumerate(scenes) if s.get("recite")]

    step("Joining the scenes")
    path = assembler.concat(composed, name)
    step("Laying in the narration")
    path = assembler.mux_voice(path, voices, starts, total)
    step("Adding the bed")
    path = assembler.add_music(path, total, silence=quiet,
                               policy=plan_of["music"])
    step(f"Video written: {path}  ({total:.1f}s)")
    return path, total


def _log(spec: dict, results: dict, kind: str) -> None:
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
        # Which kind of video this was. The alternation only needs the COUNT,
        # but without this the log cannot answer "what did we post last week"
        # for either half of the channel.
        "kind": kind,
        # The pillar is logged because the rotation reads the log back: it
        # picks tomorrow's pillar from how many videos exist, and picks the
        # topic by skipping what is already here.
        "pillar": spec.get("pillar", ""),
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
    ap.add_argument("--pillar", help="with --topic: which pillar it belongs to, "
                                     "which picks the background")
    ap.add_argument("--kind", choices=sorted(KINDS),
                    help="force today's kind instead of alternating")
    args = ap.parse_args()
    _utf8_console()

    # Before anything is generated or paid for. A missing Urdu font does not
    # fail the run, it ships a video of empty boxes — success in every log line.
    probe_fonts()
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    kind = _kind_for_today(args.kind)
    plan_of = KINDS[kind]
    step(f"Today is a {kind} day  (post #{_published() + 1} on {CHANNEL_NAME})")

    if kind == "scripture":
        # `--topic "quran 94:5"` / `--topic "hadith 5907"`, or the queue's next.
        writer = plan_of["writer"]
        if args.topic:
            entry = writer.parse_key(args.topic)
            pillar = args.pillar or ("quran" if entry.get("quran") else "hadith")
        else:
            entry, pillar = writer.next_entry()
        topic = writer.entry_key(entry)
        step(f"Today: {topic}   [{pillar}]")
        spec = writer.build_spec(entry, pillar)
    else:
        if args.topic:
            topic, pillar = args.topic, (args.pillar or NICHE)
        else:
            topic, pillar = content.next_topic()
        step(f"Topic: {topic}   [{pillar}]")
        # The habit and text kinds draw from the same topic queue — the
        # subjects are the same, only the shape of the video differs — but
        # they build a spec differently, so the writer comes off the kind
        # rather than being hardcoded to content.
        if kind == "text":
            spec = content_text.build_spec(topic, pillar)
        else:
            spec = content.write_script(topic, pillar)
    plan_of["guard"].check(spec)

    name = f"{kind}_{datetime.now().strftime('%Y%m%d')}"
    # The exact script that produced this file, saved beside it. When a video
    # performs, the only useful question is what was in it.
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    path, total = build(spec, name, pillar, kind)

    if not args.post:
        print("\nDRY RUN — nothing was posted. Watch the file above, "
              "then re-run with --post.")
        return 0

    # Imported here so a dry run needs no credentials at all — otherwise the
    # thing being previewed cannot be previewed on a fresh clone.
    results, failures, skipped = {}, [], []
    # A wellness video carries a medical disclaimer. A scripture video carries
    # its sources, which is the thing a viewer of that channel actually needs
    # in order to check it — and the thing that lets someone who knows better
    # tell us we got it wrong.
    tail = (guard_islamic.disclaimer(spec) if kind == "scripture"
            else guard.DISCLAIMER_UR)
    caption = spec.get("caption", "") + "\n\n" + tail

    # A platform with no credentials is SKIPPED, not failed. Those two states
    # look the same in a stack trace and are completely different problems: one
    # is "you have not set this up yet", the other is "the thing you set up is
    # broken". Run #3 built a perfectly good video and then exited 1 because
    # the Page did not exist yet, which is a red tick for no reason.
    import poster_fb_reels
    import poster_youtube_shorts

    if not poster_fb_reels.configured():
        skipped.append("facebook (no FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN)")
    else:
        try:
            results["facebook"] = poster_fb_reels.post_to_fb_reels(path, caption)
            print("  Facebook Reel published")
        except Exception as e:
            failures.append(f"facebook: {e}")
            print(f"  Facebook failed: {e}")

    if not poster_youtube_shorts.configured():
        skipped.append("youtube (no YOUTUBE_* secrets)")
    else:
        try:
            results["youtube"] = poster_youtube_shorts.post_to_youtube_shorts(
                path, spec)
        except Exception as e:
            failures.append(f"youtube: {e}")
            print(f"  YouTube failed: {e}")

    _log(spec, results, kind)

    if skipped:
        print("\nSkipped (not set up yet): " + "; ".join(skipped))
    # Any CONFIGURED platform failing fails the job. The sibling repo only
    # fails when ALL platforms fail, and that is exactly what hid a broken
    # poster for a month behind a green tick.
    if failures:
        print("\nFAILED: " + "; ".join(failures))
        return 1
    if not results:
        print("\nNothing was published — no platform is configured yet. "
              "The video is in out/ and as the run's artifact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
