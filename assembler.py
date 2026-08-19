"""
assembler.py
Composite, join, narrate, score. Everything ffmpeg does after the browser.

The order is fixed and each step assumes the last one was exact: the text
layers come out of renderer.py at a known frame count, so the scene durations
main.py planned are the durations that actually exist on disk, so the voice
offsets computed against that plan land where they were meant to. Nothing here
measures a file to find out how long it turned out to be.
"""
import os
import random
import subprocess

from config import (
    WIDTH, HEIGHT, FPS, TEMP_DIR, OUT_DIR, MUSIC_DIR,
    VOICE_TARGET_LUFS, MUSIC_BED_LUFS, DUCK_THRESHOLD, DUCK_RATIO,
    AUDIO_SAMPLE_RATE,
)

# What the background is when Pixabay gave us nothing. The brand's dark blue,
# not black: a missing background has to look like a choice, not like a bug.
FALLBACK_BG = "0x0A1628"

# How far out of focus the footage sits. 0 turns the grade off entirely.
# 2, down from 9 and then 7. The blur was doing a job the TYPE should be doing:
# it bought contrast by destroying the picture, and what came back looked like a
# grey rectangle with words on it. The type now carries its own dark outline and
# a deep drop shadow (see the shadow stack in templates/scene.py), which holds
# on any footage — so the footage gets to be footage. A whisper of softness is
# kept rather than zero: it costs nothing and it stops H.264 spending its
# bitrate on leaf detail nobody is looking at. BG_BLUR=0 turns it off.
BG_BLUR = float(os.environ.get("BG_BLUR") or 2)

# Per FRAME, not per second — zoompan counts frames. 0.0011 at 25fps is about
# 2.75% of scale a second, so a seven-second scene travels roughly a fifth of
# the way to the cap. Slow enough that nobody can name what is moving, fast
# enough that the frame is never the same twice.
KEN_BURNS_RATE = float(os.environ.get("KEN_BURNS_RATE") or 0.0011)
KEN_BURNS_MAX = float(os.environ.get("KEN_BURNS_MAX") or 1.12)

# Flattens the bed's own dynamics before it is levelled and ducked. 4:1 above
# roughly -24 dBFS, slow enough not to breathe on the beat.
MUSIC_TAME = os.environ.get("MUSIC_TAME") or (
    "acompressor=threshold=-24dB:ratio=4:attack=80:release=600:makeup=2")

# A track plays on a public Page under the channel's name, so every file here
# needs a licence someone actually read. A track with no entry is SKIPPED, not
# played with a shrug — the sibling repo carries four files that arrived in a
# merge with no attribution and no licence checked, and they have been sitting
# in its music folder ever since.
MUSIC_ATTRIBUTION: dict[str, str] = {
    # Beds carried over from the Time Lens project. Confirm before the first
    # public post that these are the generated beds we own outright and not a
    # licensed third-party track — the credit line below is what goes out with
    # every video, and it is a claim, not a placeholder. Until that is
    # confirmed they are not the default for anything: the policy below picks
    # one of the two generated beds instead, and those have no such question
    # hanging over them.
    "timelens_bed_choir.mp3": "Music: original score",
    "timelens_bed_choir_dark.mp3": "Music: original score",
    "timelens_bed_swell.mp3": "Music: original score",
    # Written by make_ambience.py out of ffmpeg's own noise generator. Not
    # music: filtered brown noise, no pitch, no beat, no melody. Its licence
    # is that this repository made it, which is the only provenance that needs
    # no checking.
    "ambient_room.mp3": "Ambience: generated for this channel",
    "ambient_night.mp3": "Ambience: generated for this channel",
}


def _run(args: list[str], what: str) -> None:
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}): "
                           f"{p.stderr.decode(errors='replace')[-700:]}")


def compose_scene(layer_mov: str, bg_path: str | None, bg_offset: float,
                  duration: float, name: str, index: int = 0) -> str:
    """Lay one scene's alpha text layer over the background footage.

    `bg_offset` is where in the clip this scene starts. Passing a running
    offset — rather than restarting the clip each scene — is what makes the
    background continuous across the cuts, which in turn is why the scenes can
    be joined with a hard cut and still read as one shot.

    The slow drift is a sine, not a linear pan: a linear pan reaches the edge
    of its crop margin and stops dead, and the stop is more noticeable than the
    movement ever was.

    On top of the drift, each scene pushes in or pulls out — alternating, by
    `index`. This is the fix for the complaint that the finished videos had no
    life in them. The drift alone moves the frame sideways by about fifty
    pixels over ten seconds, which on a phone is indistinguishable from a still
    image; a continuous change of SCALE reads as movement even when it is
    slower than that, and alternating its direction means two consecutive
    scenes do not feel like one long slow creep in the same direction.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    out = os.path.join(TEMP_DIR, f"{name}_composed.mp4")

    over_w, over_h = int(WIDTH * 1.10), int(HEIGHT * 1.10)
    drift = (f"scale={over_w}:{over_h}:force_original_aspect_ratio=increase,"
             f"crop={WIDTH}:{HEIGHT}:"
             f"x=(iw-ow)/2+sin(t/9)*{(over_w - WIDTH) // 2}:"
             f"y=(ih-oh)/2+cos(t/13)*{(over_h - HEIGHT) // 3}")

    # `in` is the frame count within THIS scene's own segment, so every scene
    # gets its own move rather than inheriting where the last one stopped. The
    # first scene pushes in hardest: it is the two seconds that decide whether
    # anyone sees the rest.
    rate = KEN_BURNS_RATE * (1.6 if index == 0 else 1.0)
    if index % 2 == 0:
        zoom = f"min(1+{rate:.5f}*in,{KEN_BURNS_MAX})"
    else:
        zoom = f"max({KEN_BURNS_MAX}-{rate:.5f}*in,1)"
    ken = (f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':"
           f"y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS}")

    # Blurred and pulled down before the text goes on. The first live video ran
    # over a rain-on-glass clip: thousands of little high-contrast highlights,
    # directly behind the headline, and the type had to fight every one of
    # them. The background's job here is mood, not detail — nobody watches a
    # text video for the footage — and out of focus it also stops competing
    # with the words.
    #
    # The numbers were softened after the first run of finished videos: sigma 9
    # with saturation .72 and brightness -.10 did not read as "out of focus
    # behind type", it read as a grey rectangle, and a grey rectangle is what
    # "there is no life in these" looks like. The scrim in templates/scene.py
    # is what actually buys the contrast under the text — it is a gradient
    # exactly where the type sits — so the picture itself does not also have to
    # be flattened. The hook keeps more detail still: frame one is the only
    # frame most viewers will ever see, and it should look like something.
    blur = BG_BLUR * (0.6 if index == 0 else 1.0)
    grade = (f"gblur=sigma={blur:g},"
             # Barely a grade now. Green mountain footage in daylight is the
             # point of the picture; pulling it down half a stop and desaturating
             # it was how the old "no life in these" look was made.
             f"eq=brightness=-0.02:saturation=1.02:contrast=1.04,"
             # Pulls the corners down so the eye lands in the middle of the
             # frame, where the type is. Cheap, and it is most of what
             # separates footage-with-text-on-it from a shot.
             f"vignette=PI/6")

    if bg_path:
        src = ["-stream_loop", "-1", "-ss", f"{bg_offset:.3f}", "-i", bg_path]
        bg_chain = f"[0:v]{drift},{ken},{grade},fps={FPS},format=rgba[bg]"
    else:
        # Not an error path worth failing on, but it must look deliberate
        # rather than broken: the brand's own dark blue, not black.
        src = ["-f", "lavfi", "-i",
               f"color=c={FALLBACK_BG}:s={WIDTH}x{HEIGHT}:r={FPS}"]
        bg_chain = "[0:v]format=rgba[bg]"

    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          *src, "-i", layer_mov,
          "-filter_complex",
          f"{bg_chain};[bg][1:v]overlay=format=auto:eof_action=pass[v]",
          "-map", "[v]", "-t", f"{duration:.3f}",
          "-c:v", "libx264", "-preset", "medium", "-crf", "19",
          "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", out],
         f"compose {name}")
    return out


def concat(paths: list[str], name: str) -> str:
    """Join the composed scenes.

    Re-encoded rather than stream-copied. The segments come from separate
    encodes, and the concat demuxer needs identical timebases to copy safely —
    a mismatch there makes a file that plays for one viewer and stalls for
    another, which is the worst possible way to find a bug.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{name}.mp4")
    listing = os.path.join(TEMP_DIR, f"{name}_segments.txt")
    with open(listing, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p).replace(os.sep, '/')}'\n")
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          "-f", "concat", "-safe", "0", "-i", listing,
          "-c:v", "libx264", "-preset", "medium", "-crf", "19",
          "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
          "-movflags", "+faststart", out], f"concat {name}")
    os.remove(listing)
    return out


def mux_voice(video_path: str, clips: list[dict], starts: list[float],
              total: float) -> str:
    """Lay each narration clip in at the moment its scene begins.

    adelay + amix rather than a plain concat, because the gaps are load-bearing:
    the silence between lines is the time a viewer spends reading the headline
    that just landed.
    """
    if not clips:
        return video_path
    inputs, filters, labels = [], [], []
    for i, (clip, start) in enumerate(zip(clips, starts)):
        path = clip.get("audio_path")
        if not path:
            continue
        inputs += ["-i", path]
        delay = max(0, int(start * 1000))
        filters.append(f"[{len(inputs) // 2}:a]adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    if not labels:
        return video_path

    chain = (";".join(filters) + ";" + "".join(labels)
             + f"amix=inputs={len(labels)}:dropout_transition=0:normalize=0[m];"
             + f"[m]loudnorm=I={VOICE_TARGET_LUFS}:TP=-2:LRA=11,"
               f"aresample={AUDIO_SAMPLE_RATE}[aout]")

    out = video_path.replace(".mp4", "_voiced.mp4")
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          "-i", video_path, *inputs, "-filter_complex", chain,
          "-map", "0:v", "-map", "[aout]", "-t", f"{total:.3f}",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-ar", str(AUDIO_SAMPLE_RATE), "-movflags", "+faststart", out],
         "mux voice")
    os.replace(out, video_path)
    return video_path


# The bed, pinned rather than rotated. Measured with ebur128 — all three files
# sit at the same -14.4 LUFS, so "the loudest" does not separate them; what
# separates them is movement:
#
#   timelens_bed_choir_dark.mp3   LRA  2.9 LU   flattest
#   timelens_bed_choir.mp3        LRA  6.4 LU
#   timelens_bed_swell.mp3        LRA 16.5 LU   the one that builds
#
# swell is the one that reads as "fast and loud", and it is the pick — but a
# 16.5 LU swing under continuous narration is a real problem: it vanishes in
# the quiet passages and climbs over the voice in the loud ones, and the
# sidechain ducker pumps chasing it. `MUSIC_TAME` below is what makes it usable
# rather than just louder.
MUSIC_TRACK = os.environ.get("MUSIC_TRACK") or ""

# What is allowed under the voice, chosen PER VIDEO rather than per channel —
# because the channel now alternates, and the answer is different on the two
# kinds of day:
#
#   "bed"      a scored music bed. The habit videos.
#   "ambient"  room tone only — see make_ambience.py. This is what a scripture
#              day gets. Instrumental music under recitation is not something
#              an Urdu Islamic video can do: a good part of the audience holds
#              it impermissible, and a melody under an ayah competes with the
#              ayah either way. Silence alone reads as a broken upload, so what
#              plays is air, not music.
#   "none"     nothing at all. NO_MUSIC=1 forces this from anywhere.
#
# main.py passes the day's policy down; this is only the default for a caller
# that does not.
DEFAULT_MUSIC_POLICY = ("none" if os.environ.get("NO_MUSIC") else
                        (os.environ.get("MUSIC_POLICY") or "bed"))


def _policy(policy: str | None) -> str:
    """NO_MUSIC always wins, whatever the caller asked for."""
    if os.environ.get("NO_MUSIC"):
        return "none"
    return policy or DEFAULT_MUSIC_POLICY
POLICY_DEFAULT = {
    "bed": "timelens_bed_swell.mp3",
    "ambient": "ambient_night.mp3",
}


def pick_music(policy: str | None = None) -> tuple[str | None, str]:
    """The pinned track, or the first licensed one if it is missing."""
    policy = _policy(policy)
    if policy == "none":
        print("  music policy is 'none' — the voice carries the video alone")
        return None, ""
    if not os.path.isdir(MUSIC_DIR):
        return None, ""
    licensed = [fn for fn in sorted(os.listdir(MUSIC_DIR))
                if fn.lower().endswith((".mp3", ".m4a", ".wav"))
                and fn in MUSIC_ATTRIBUTION]
    for fn in sorted(os.listdir(MUSIC_DIR)):
        if (fn.lower().endswith((".mp3", ".m4a", ".wav"))
                and fn not in MUSIC_ATTRIBUTION):
            print(f"  skipping {fn}: no entry in assembler.MUSIC_ATTRIBUTION. "
                  f"Add the licence line before this track can be used.")
    if not licensed:
        return None, ""

    # An explicit MUSIC_TRACK wins; otherwise the policy's own bed. The
    # fallback deliberately stays INSIDE the policy — an "ambient" channel
    # whose file is missing gets no bed rather than the first mp3 in the
    # folder, because for that channel the wrong file is worse than none.
    wanted = MUSIC_TRACK or POLICY_DEFAULT.get(policy, "")
    if wanted in licensed:
        fn = wanted
    elif policy == "ambient":
        print(f"  {wanted} is not in data/music — run make_ambience.py. "
              f"Shipping without a bed rather than substituting music.")
        return None, ""
    else:
        fn = licensed[0]
        print(f"  {wanted} not in data/music — using {fn}")
    print(f"  bed: {fn}  [policy: {policy}]")
    return os.path.join(MUSIC_DIR, fn), MUSIC_ATTRIBUTION[fn]


def add_music(video_path: str, duration: float,
              silence: list[tuple[float, float]] | None = None,
              policy: str | None = None) -> str:
    """Duck a music bed under the narration.

    Sidechained rather than set to a fixed low volume: a constant level either
    fights the voice or vanishes under it, while ducking lets the bed sit back
    for a line and come up in the gap — and the gaps are where the headline is
    being read.

    `silence` is a list of (start, end) windows in which the bed is muted
    outright rather than ducked. A scripture day passes the recitation's own
    window: ducking is not enough there, because ducking is a level
    decision and this is not one. Nothing plays under the Qur'an.
    """
    track, credit = pick_music(policy)
    if not track:
        print("  no licensed music track — shipping without a bed")
        return video_path

    has_audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True).stdout.strip()

    fade_out = max(duration - 2.0, 0)
    # Tamed BEFORE it is levelled. loudnorm sets an average; it does not stop a
    # 16.5 LU track from disappearing under one line and climbing over the
    # next. The compressor pulls the swings toward the middle first, so the bed
    # arrives at a roughly constant level and the sidechain ducker below has
    # one job — getting out of the way of speech — instead of also chasing the
    # music's own build.
    bed = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{duration:.3f},"
           f"{MUSIC_TAME},"
           f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2,"
           f"loudnorm=I={MUSIC_BED_LUFS}:TP=-8:LRA=5")

    # Muted last, after levelling, so loudnorm cannot bring the silence back
    # up — and as a fade out and a fade back in rather than a switch, because
    # a bed that stops dead is a click, and a click before an ayah is worse
    # than the bed would have been.
    ramp = 0.5
    for start, end in (silence or []):
        out_at = max(start - ramp, 0.0)
        back_at = min(end, max(duration - ramp, 0.0))
        if back_at <= out_at:
            continue
        bed += (f",afade=t=out:st={out_at:.3f}:d={ramp}"
                f",afade=t=in:st={back_at:.3f}:d={ramp}")
        print(f"  bed silent {out_at:.1f}s–{back_at + ramp:.1f}s")

    if has_audio:
        chain = (f"[0:a]aresample={AUDIO_SAMPLE_RATE},asplit=2[v][sc];{bed}[b];"
                 f"[b][sc]sidechaincompress=threshold={DUCK_THRESHOLD}:"
                 f"ratio={DUCK_RATIO}:attack=20:release=400[duck];"
                 f"[v][duck]amix=inputs=2:duration=first:normalize=0,"
                 f"loudnorm=I={VOICE_TARGET_LUFS - 1}:TP=-2:LRA=11,"
                 f"aresample={AUDIO_SAMPLE_RATE}[aout]")
    else:
        chain = f"{bed},aresample={AUDIO_SAMPLE_RATE}[aout]"

    out = video_path.replace(".mp4", "_music.mp4")
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
          "-i", video_path, "-i", track, "-filter_complex", chain,
          "-map", "0:v", "-map", "[aout]", "-t", f"{duration:.3f}",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-movflags", "+faststart", out], "add music")
    os.replace(out, video_path)
    print(f"  {credit}")
    return video_path
