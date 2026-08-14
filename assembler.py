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
import subprocess

from config import (
    WIDTH, HEIGHT, FPS, TEMP_DIR, OUT_DIR, MUSIC_DIR,
    VOICE_TARGET_LUFS, MUSIC_BED_LUFS, DUCK_THRESHOLD, DUCK_RATIO,
    AUDIO_SAMPLE_RATE,
)

# What the background is when Pixabay gave us nothing. The brand's dark blue,
# not black: a missing background has to look like a choice, not like a bug.
FALLBACK_BG = "0x0A1628"

# A track plays on a public Page under the channel's name, so every file here
# needs a licence someone actually read. A track with no entry is SKIPPED, not
# played with a shrug — the sibling repo carries four files that arrived in a
# merge with no attribution and no licence checked, and they have been sitting
# in its music folder ever since.
MUSIC_ATTRIBUTION: dict[str, str] = {
    # "some_track.mp3": 'Music: "Some Track" by Artist — CC BY 4.0',
}


def _run(args: list[str], what: str) -> None:
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}): "
                           f"{p.stderr.decode(errors='replace')[-700:]}")


def compose_scene(layer_mov: str, bg_path: str | None, bg_offset: float,
                  duration: float, name: str) -> str:
    """Lay one scene's alpha text layer over the background footage.

    `bg_offset` is where in the clip this scene starts. Passing a running
    offset — rather than restarting the clip each scene — is what makes the
    background continuous across the cuts, which in turn is why the scenes can
    be joined with a hard cut and still read as one shot.

    The slow drift is a sine, not a linear pan: a linear pan reaches the edge
    of its crop margin and stops dead, and the stop is more noticeable than the
    movement ever was.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    out = os.path.join(TEMP_DIR, f"{name}_composed.mp4")

    over_w, over_h = int(WIDTH * 1.10), int(HEIGHT * 1.10)
    drift = (f"scale={over_w}:{over_h}:force_original_aspect_ratio=increase,"
             f"crop={WIDTH}:{HEIGHT}:"
             f"x=(iw-ow)/2+sin(t/9)*{(over_w - WIDTH) // 2}:"
             f"y=(ih-oh)/2+cos(t/13)*{(over_h - HEIGHT) // 3}")

    if bg_path:
        src = ["-stream_loop", "-1", "-ss", f"{bg_offset:.3f}", "-i", bg_path]
        bg_chain = f"[0:v]{drift},fps={FPS},format=rgba[bg]"
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


def pick_music() -> tuple[str | None, str]:
    """The first licensed track in data/music, and its credit line."""
    if not os.path.isdir(MUSIC_DIR):
        return None, ""
    for fn in sorted(os.listdir(MUSIC_DIR)):
        if not fn.lower().endswith((".mp3", ".m4a", ".wav")):
            continue
        if fn not in MUSIC_ATTRIBUTION:
            print(f"  skipping {fn}: no entry in assembler.MUSIC_ATTRIBUTION. "
                  f"Add the licence line before this track can be used.")
            continue
        return os.path.join(MUSIC_DIR, fn), MUSIC_ATTRIBUTION[fn]
    return None, ""


def add_music(video_path: str, duration: float) -> str:
    """Duck a music bed under the narration.

    Sidechained rather than set to a fixed low volume: a constant level either
    fights the voice or vanishes under it, while ducking lets the bed sit back
    for a line and come up in the gap — and the gaps are where the headline is
    being read.
    """
    track, credit = pick_music()
    if not track:
        print("  no licensed music track — shipping without a bed")
        return video_path

    has_audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True).stdout.strip()

    fade_out = max(duration - 2.0, 0)
    bed = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{duration:.3f},"
           f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2,"
           f"loudnorm=I={MUSIC_BED_LUFS}:TP=-8:LRA=7")

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
