"""
fetch_fonts.py
Downloads the two Urdu faces into ./fonts. Run once, then commit them.

Commit them. Do not load these from Google Fonts at render time: the runner
occasionally cannot reach fonts.googleapis.com, the page falls back to a Latin
face, and every Urdu glyph renders as an empty box — in a video that uploads,
publishes and reports success. The whole point of vendoring is that the run
either has the right type or does not start (see renderer.probe_fonts).

Both faces are SIL Open Font License 1.1, which permits redistribution inside
this repository as long as the licence file travels with them — which is why
OFL.txt is fetched too.
"""
import os

import requests

RAW = "https://raw.githubusercontent.com/google/fonts/main"
FILES = {
    "NotoNastaliqUrdu-Bold.ttf":
        f"{RAW}/ofl/notonastaliqurdu/NotoNastaliqUrdu%5Bwght%5D.ttf",
    "NotoSansArabic-SemiBold.ttf":
        f"{RAW}/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf",
    "OFL.txt":
        f"{RAW}/ofl/notonastaliqurdu/OFL.txt",
}


def main() -> int:
    os.makedirs("fonts", exist_ok=True)
    for name, url in FILES.items():
        dest = os.path.join("fonts", name)
        if os.path.exists(dest):
            print(f"  have {name}")
            continue
        print(f"  fetching {name}")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
    print("Fonts in ./fonts — commit them so CI has them too.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
