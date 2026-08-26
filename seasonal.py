# -*- coding: utf-8 -*-
"""
seasonal.py
Topics that follow what people are actually living through today.

WHY
  The topic queue is a fixed list, worked through in order, and it has no idea
  what day it is. So a card about drinking water goes out on the first Friday
  of Ramadan, and one about saving money goes out on the 20th when the money is
  already gone. The subjects are fine; the timing is nobody's.

  This is the cheap half of "make it feel current". No trends API, no news
  feed, nothing to go stale or go wrong: the calendar already knows that it is
  Friday, that it is Ramadan, that it is the first of the month and salary has
  landed, that it is exam season, that it is the middle of a Lahore winter.
  Those are the things a viewer is living through, and a card that names one
  reads as written today rather than written whenever.

WHY NOT ACTUAL TRENDING TOPICS
  Considered and rejected. What trends in Pakistan on a given day is mostly
  politics, a disaster, a crime or a celebrity — every one of which this
  channel's own writing rules already forbid, for good reasons that have not
  changed. Chasing a trend would also put a six-follower page in the same
  results as every large account covering the same thing, which is the one
  fight it cannot win. Seasons give the "written today" feeling without any of
  that.

HOW IT DEGRADES
  The Hijri rules need one API call. If it fails — and it will, eventually —
  those rules are skipped and the Gregorian ones still run. If nothing matches
  at all, the caller falls back to the ordinary queue, which is what happens on
  most days anyway. A season is a nudge, never a requirement.
"""
import datetime as dt
import json
import os
import urllib.request

HIJRI_URL = "https://api.aladhan.com/v1/gToH/{d:02d}-{m:02d}-{y}"
HIJRI_TIMEOUT = float(os.environ.get("HIJRI_TIMEOUT") or 12)

# Hijri months, by number, that this file cares about.
RAMADAN, SHAWWAL, DHUL_HIJJAH, MUHARRAM, RABI_AWWAL = 9, 10, 12, 1, 3


def hijri_today(today: dt.date | None = None) -> tuple[int, int] | None:
    """(hijri day, hijri month number), or None if it cannot be fetched.

    A network call for a date is not free, but it is one call a day against a
    public endpoint, and the alternative is either a new dependency or a hand
    rolled conversion that will be a day out somewhere and nobody will notice.
    """
    today = today or dt.date.today()
    try:
        url = HIJRI_URL.format(d=today.day, m=today.month, y=today.year)
        with urllib.request.urlopen(url, timeout=HIJRI_TIMEOUT) as r:
            h = json.loads(r.read().decode("utf-8"))["data"]["hijri"]
        return int(h["day"]), int(h["month"]["number"])
    except Exception as e:
        print(f"  hijri date unavailable ({type(e).__name__}) — "
              f"seasonal rules that need it are skipped")
        return None


# Each season is a list of topics. They are written the way the topic queue's
# entries are written — a subject, not a script — because they go to the same
# writer.
#
# Ordered most specific first: the checks run in this order and the first match
# wins. Ramadan beats Friday, Friday beats winter, winter beats payday.
SEASONS: dict[str, list[str]] = {
    "ramadan": [
        "roze mein neend poori kaise ho",
        "sehri ke baad so jaana theek hai ya nahi",
        "iftar par itna kha lena ke taraweeh bhaari lage",
        "ramzan mein ghusse par qaabu",
        "aakhri ashra aur neend ka jhagra",
    ],
    "eid": [
        "eid ke din rishtedaron se milna",
        "eid ke baad wapas apni routine par aana",
    ],
    "hajj_days": [
        "un dinon mein jab hum hajj par nahi hote",
        "qurbani ke gosht ki taqseem",
    ],
    "muharram": [
        "sabr ka matlab kya hai",
        "gham ke dinon mein apna khayal",
    ],
    "rabi_awwal": [
        "seerat se aik chhoti aadat",
        "narmi se baat karna",
    ],
    "jumma": [
        "jumma ke din ka pehla ghanta",
        "hafte bhar ki thakan aur jumma ki dopeher",
        "jumma ko ghar walon ke liye waqt",
    ],
    "payday": [
        "tankhwah aate hi sab se pehla kaam",
        "mahine ke pehle hafte mein kharch",
        "udhaar utaarne ka sab se acha waqt",
    ],
    "month_end": [
        "mahine ke aakhri dinon ki tangi",
        "agle mahine ke liye aaj kya likh lein",
    ],
    "exams": [
        "imtihan ke dinon mein neend",
        "bachon ke result ka intezar",
        "parhai ke darmiyan chhoti breaks",
    ],
    "winter": [
        "sardi ki raat mein jaldi so jaana",
        "sardi mein subah uthna",
        "thand mein paani kam peena",
    ],
    "monsoon": [
        "barsat ke dinon mein ghar ka mood",
        "garmi aur chirchirapan",
    ],
}


def _season_for(today: dt.date, hijri: tuple[int, int] | None) -> str | None:
    """The name of the season today falls in, most specific first."""
    if hijri:
        hd, hm = hijri
        if hm == RAMADAN:
            return "ramadan"
        if hm == SHAWWAL and hd <= 3:
            return "eid"
        if hm == DHUL_HIJJAH and hd <= 13:
            return "hajj_days"
        if hm == MUHARRAM and hd <= 12:
            return "muharram"
        if hm == RABI_AWWAL:
            return "rabi_awwal"

    # Friday. Named after the Hijri checks so Ramadan Fridays read as Ramadan,
    # which is what they are to the person watching.
    if today.weekday() == 4:
        return "jumma"

    # Salary lands at the start of the month here, and the last week is when
    # it is gone. Both are felt, and neither is felt on the 12th.
    if today.day <= 3:
        return "payday"
    if today.day >= 26:
        return "month_end"

    # Pakistan's school and university exams cluster in these two windows.
    if today.month in (5, 6) or today.month == 11:
        return "exams"
    if today.month in (12, 1, 2):
        return "winter"
    if today.month in (7, 8):
        return "monsoon"
    return None


def topic_for(today: dt.date | None = None, posted: int = 0,
              exclude: set[str] | None = None) -> tuple[str, str] | None:
    """(topic, season) for today, or None to fall back to the ordinary queue.

    `posted` rotates within the season so a channel does not run the same
    Friday card every Friday, and `exclude` drops anything already used — a
    repeat is worse than falling through to the normal queue.
    """
    today = today or dt.date.today()
    forced = os.environ.get("SEASON")
    season = forced or _season_for(today, hijri_today(today))
    if not season:
        return None
    if season not in SEASONS:
        raise ValueError(f"No season named {season!r}. Have: "
                         + ", ".join(SEASONS))

    pool = [t for t in SEASONS[season] if t not in (exclude or set())]
    if not pool:
        print(f"  season {season}: every topic already used — "
              f"falling back to the queue")
        return None
    return pool[posted % len(pool)], season
