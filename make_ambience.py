"""
make_ambience.py
Generates the beds this repo is allowed to use, from nothing but ffmpeg.

    python make_ambience.py

Two problems solved by one script.

The first is licensing. data/music carries three beds inherited from the Time
Lens project, and assembler.MUSIC_ATTRIBUTION has been carrying a note since
they arrived saying somebody must confirm what they actually are before the
first public post. A track that plays on a Page under the channel's name is a
claim; "it was in the folder" is not a licence. Everything this script writes
is synthesised here, from ffmpeg's own signal generators, so its provenance is
this file and there is nothing to confirm.

The second is the scripture channel. Instrumental music under recitation is
not something an Urdu Islamic channel can do — a good part of the audience
holds it to be impermissible outright, and even setting that aside, a melody
under an ayah competes with it. But silence behind a video reads as a broken
upload. What is wanted is *room* — the sound of air in a large quiet space —
which is not music by anyone's definition, and which is what `ambient_room`
and `ambient_night` are: filtered noise, no pitch, no beat, no melody.

    ambient_room   a soft, wide, low hiss. Reads as a large still room.
    ambient_night  the same, darker and thinner, with a slow breath in it.

Both are SEEDED, so regenerating them anywhere — a fresh clone, a CI runner —
produces byte-for-byte the same bed. Without a seed the channel's ambience
would quietly be a different noise field every time somebody deleted the files,
which is the kind of drift nobody notices and nobody can explain later.

Both are written as seamless 60-second loops. No fades are baked in: the bed
is looped and faded by assembler.add_music, and a fade inside the file would
put a dip at every loop point. Written as mp3 rather than wav only so they can
live in the repository — a minute of 48kHz stereo PCM is eleven megabytes.
"""
import os
import subprocess
import sys

MUSIC_DIR = "data/music"
SECONDS = 60


BEDS = {
    # Brown noise is noise weighted heavily to the low end — the spectrum of
    # air and distance rather than the spectrum of a hiss. Lowpassed twice to
    # take the top off it, then very slowly swelled so the bed breathes
    # instead of sitting there as a flat wall.
    # ffmpeg's tremolo will not go below 0.1 Hz, which is a ten-second cycle —
    # slow enough to read as a room breathing rather than as an effect.
    "ambient_room.mp3": (
        "anoisesrc=color=brown:amplitude=0.5:seed=20260819:"
        "duration={secs}:sample_rate=48000,"
        "lowpass=f=520,lowpass=f=900,"
        "tremolo=f=0.1:d=0.22,"
        "volume=0.5"
    ),
    # Darker: more of the low end kept, the last of the top gone, and a slower
    # swell. This is the one the scripture profile uses.
    "ambient_night.mp3": (
        "anoisesrc=color=brown:amplitude=0.45:seed=20260820:"
        "duration={secs}:sample_rate=48000,"
        "lowpass=f=320,lowpass=f=600,highpass=f=45,"
        "tremolo=f=0.1:d=0.3,"
        "volume=0.42"
    ),
}


def main() -> int:
    os.makedirs(MUSIC_DIR, exist_ok=True)
    for name, chain in BEDS.items():
        dest = os.path.join(MUSIC_DIR, name)
        if os.path.exists(dest):
            print(f"  have {name}")
            continue
        graph = chain.format(secs=SECONDS)
        print(f"  generating {name}")
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-filter_complex", graph + "[a]", "-map", "[a]",
             "-t", str(SECONDS), "-c:a", "libmp3lame", "-b:a", "192k",
             "-ar", "48000", "-ac", "2", dest],
            capture_output=True, text=True)
        if r.returncode:
            print(r.stderr.strip()[:800])
            return 1
    print(f"Beds in {MUSIC_DIR}. They are generated, so they are ours — the "
          f"attribution line in assembler.MUSIC_ATTRIBUTION says exactly that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
