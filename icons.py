"""
icons.py
Inline SVG icons, drawn from the repo itself.

Deliberately NOT emoji. The sibling repo uses HTML entities (`&#128202;`),
which resolve against whatever emoji font the machine happens to have — the
GitHub Actions runner does not have the one the author was looking at, so the
video that ships is not the video that was approved. These are outlines with
`stroke:currentColor`, so the scene's own colour drives them, they can be
animated (stroke-dasharray draws them on), and nothing is fetched at runtime.

Paths are Lucide-shaped (ISC licensed, 24x24 grid, 2px stroke). Add more as
topics need them — but see `icon()`: an unknown name is a hard error, never a
silent fallback. A generic icon shipping unnoticed is exactly the bug the
website builder repo had to fix in `732a769`.
"""

_P = {
    # sleep / rest
    "moon": "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z",
    "bed": "M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 12h4",
    "alarm": "M12 13V9M5 3 2 6M22 6l-3-3M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16z",
    "sunrise": "M12 2v6M4.2 10.2 5.6 11.6M2 18h2M20 18h2M18.4 11.6l1.4-1.4"
               "M22 22H2M16 18a4 4 0 0 0-8 0",
    # body / health-adjacent, non-clinical
    "droplet": "M12 2.7 6.5 8.2a7.8 7.8 0 1 0 11 0z",
    "footprints": "M4 16v-2.4a2.6 2.6 0 0 1 5.2 0V16a2.6 2.6 0 0 1-5.2 0z"
                  "M4 21h5.2M14.8 11V8.6a2.6 2.6 0 0 1 5.2 0V11a2.6 2.6 0 0 1-5.2 0z"
                  "M14.8 16H20",
    "heart": "M19 5.7a5 5 0 0 0-7 0l-1 1-1-1a5 5 0 0 0-7 7.1l8 8 8-8a5 5 0 0 0 0-7.1z",
    "activity": "M22 12h-4l-3 9L9 3l-3 9H2",
    "leaf": "M11 20A7 7 0 0 1 20 4c0 9-7 12-13 12M4 20c2-4 5-6 8-7",
    "apple": "M12 7c-3-4-9-2-9 4 0 5 4 10 6.5 10 1 0 1.5-.6 2.5-.6s1.5.6 2.5.6"
             "C17 21 21 16 21 11c0-6-6-8-9-4zM12 7V3",
    "dumbbell": "M6.5 6.5v11M3.5 9v5M17.5 6.5v11M20.5 9v5M6.5 12h11",
    "bowl": "M3 11h18a9 9 0 0 1-18 0zM12 11V7M9.5 7.5 12 4l2.5 3.5",
    "stairs": "M3 21h4v-4h4v-4h4V9h4V5h3M3 21v-4",
    # mind / focus
    "brain": "M9 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 1 5 3 3 0 0 0 4 3V3z"
             "M15 3a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-1 5 3 3 0 0 1-4 3V3z",
    "focus": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM3 7V4h3M18 4h3v3M21 17v3h-3M6 20H3v-3",
    # The body alone drew as a plain rounded rectangle, and at 148px in frame
    # one of the first live video that is what a viewer saw: an empty box. A
    # phone needs its earpiece and its home line to read as a phone at a
    # glance.
    "phone_off": "M17 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"
                 "M9.5 6h5M10 18.2h4M3 3l18 18",
    # money / work (second niche, kept ready)
    "wallet": "M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5"
              "a2 2 0 0 1-2-2V5M17 13h.01",
    "chart": "M3 3v18h18M7 15l4-5 3 3 5-7",
    "clock": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
    # deen — for the scripture profile. Outlines only, and nothing figurative
    # beyond a building: the channel puts an ayah on screen, so the artwork
    # around it stays furniture and never becomes the subject.
    "book_open": "M12 7v14M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4"
                 "a4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3"
                 "a3 3 0 0 0-3-3z",
    "mosque": "M12 3c-2.2 1.6-3.5 3.4-3.5 5h7c0-1.6-1.3-3.4-3.5-5zM6 21V11"
              "a6 6 0 0 1 12 0v10M3 21V9M21 21V9M2 21h20"
              "M10 21v-4a2 2 0 0 1 4 0v4",
    "lamp": "M8 2h8l4 10H4L8 2zM12 12v6M8 22h8a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2z",
    "quote": "M10 11H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v7"
             "a4 4 0 0 1-4 4M20 11h-5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4"
             "a1 1 0 0 1 1 1v7a4 4 0 0 1-4 4",
    "hands": "M7 21c-1.5-3-2-5-2-8V8a1.5 1.5 0 0 1 3 0M17 21c1.5-3 2-5 2-8V8"
             "a1.5 1.5 0 0 0-3 0M8 13V5.5a1.5 1.5 0 0 1 3 0V12"
             "M13 12V5.5a1.5 1.5 0 0 1 3 0V13",
    # the ibrat story. The two halves of that format are told with colour
    # (see content_ibrat.TONE); these carry the beat.
    #
    # A balance for the akhirat scene, because the mizan is the image that
    # scene is already reaching for and a star or a clock there would be
    # furniture standing in for it. A crack running down for what a wrong turn
    # costs — the split is the point, and it reads at a glance where a frown or
    # a broken heart would read as a sticker.
    "scales": "M12 3v18M8 21h8M5 7h14M12 3a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8z"
              "M5 7 2 13a3 3 0 0 0 6 0zM19 7l-3 6a3 3 0 0 0 6 0z",
    # Branches, not just a zigzag. The first version was a single narrow line
    # down the middle and at 110px inside the disc it read as a lightning bolt
    # — which is weather, not consequence. The two short forks are what make it
    # a split, and they are what fill the grid the other icons fill.
    "crack": "M13 2 10 9l4 2-3 5 2 6M10.6 10.2 6.5 13M14.2 16.4 18 14.2",
    # narrative furniture
    "alert": "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3"
             "L13.7 3.9a2 2 0 0 0-3.4 0z",
    "check": "M20 6 9 17l-5-5",
    "arrow": "M5 12h14M13 6l6 6-6 6",
    "star": "m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.9L12 17.8 5.8 21l1.2-6.9-5-4.9 6.9-1z",
}

# Which icon a scene role gets when the writer does not name one. Roles are
# fixed by the format, so this can never miss.
ROLE_DEFAULT = {
    "hook": "alert",
    "problem": "alert",
    "cause": "brain",
    "tactic": "check",
    "action": "arrow",
    "follow": "star",
    # the two newer habit shapes
    "ghalti": "alert",
    "sudhaar": "check",
    "pehle": "clock",
    "baad": "sunrise",
    "wajah": "brain",
    # the ibrat story's roles
    "neki": "hands",
    # What a small good thing turns into, rather than a tick confirming it
    # happened — the scene is about the growth, not the deed.
    "natija_neki": "leaf",
    "gunah": "alert",
    "natija_gunah": "crack",
    "akhirat": "scales",
    # the scripture profile's roles
    "ayah": "book_open",
    "hadith": "quote",
    "tarjuma": "book_open",
    "tashreeh": "lamp",
    "amal": "hands",
}

# The scripture channel shares the habit channel's roles for everything that is
# not verbatim — hook, tashreeh, amal, follow all render through the same
# template. That is fine until the ICON comes along: "hook" defaults to the
# hazard triangle, which is right above a symptom on a sleep video and badly
# wrong above an ayah about ease after hardship. The verse that carried this
# channel's only engaging video opened with a danger sign.
#
# Only the roles that need to differ are listed. Anything absent falls through
# to ROLE_DEFAULT, so the scripture profile does not have to restate the roles
# that were already right.
SCRIPTURE_DEFAULT = {
    # No icon at all. The hook is six words of Nastaliq holding in silence
    # before the qari begins, and a badge above it is one more thing competing
    # with the only thing on screen.
    "hook": None,
    "follow": "star",
}


def default_for(role: str, profile: str = "") -> str | None:
    """The icon a role gets when the writer names none.

    profile picks the map; an unknown profile is the habit one, which is the
    behaviour every existing caller already had.
    """
    if profile == "scripture" and role in SCRIPTURE_DEFAULT:
        return SCRIPTURE_DEFAULT[role]
    return ROLE_DEFAULT.get(role)


def icon(name: str, size: int = 96) -> str:
    """Return an inline <svg> for `name`. Unknown names raise, on purpose."""
    if name not in _P:
        raise KeyError(
            f"No icon named {name!r}. Add its path to icons._P, or use one of: "
            + ", ".join(sorted(_P))
        )
    return (
        f'<svg class="ic" viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{_P[name]}"/></svg>'
    )


def known() -> list[str]:
    return sorted(_P)
