"""
build_queue.py
Fills data/islamic_queue.json with entries that will actually fit a Short.

    python build_queue.py            # top the queue up
    python build_queue.py --show     # print what is in it and what has run

The queue is the input to the scripture channel exactly as data/topics.json is
the input to the wellness one, and for the same reason: a model asked every
morning to pick a verse converges, and on this channel it would converge on
whatever it has seen most, which is not a defensible way to choose what
scripture reaches people. So the queue is chosen once and drained one entry a
day. This script does the choosing MECHANICALLY — it does not ask a model
anything — and it filters on the two things that decide whether an entry can
be a sixty-second video at all:

  length   A verse whose Urdu translation runs past ~30 words leaves no room
           for the recitation, the explanation and the follow — 30 words is
           about fifteen seconds of spoken Urdu, and the recitation and the
           written parts need the other forty-five. A hadith past ~45 words is
           a page. Both caps were set by measuring, not guessed: at 24 words
           the filter threw out most of the verses worth posting.
  grade    Only what islamic_sources.SOUND_GRADES accepts. HadeethEnc supplies
           the grade; nothing here judges one.

Hadiths are drawn from HadeethEnc category 5, فضائل و آداب — virtues and
manners. Deliberately not category 4 (فقہ), which is rulings, and not the
sub-categories about sects: a daily automated channel has no business in
either, and the writer is told the same thing in content_islamic.SYSTEM.

Verses are the list below, written by hand and kept short. Add to it. The
script checks every one against the API before it writes anything, so a typo
in a reference fails here rather than at six in the morning.
"""
import argparse
import json
import os
import sys

import islamic_sources as sources
from config import ISLAMIC_QUEUE_FILE, LOG_FILE

MAX_AYAH_WORDS = 30
MAX_HADITH_WORDS = 45

HADEETH_CATEGORY = "5"          # فضائل و آداب
HADEETH_PAGES = 6
PER_PAGE = 25

# Chosen by hand, one at a time, and NOT a walk through the mushaf. The system
# will never "do every ayah in order": most verses need a context a
# sixty-second video cannot carry, many are part of a passage that means
# something different alone, and some are about law, war or a moment in history
# where a short clip with no scholarship behind it does harm. What is here is
# the other kind — verses about how a person lives with difficulty, with
# people, with themselves. Well known, mostly short, and each one checked
# against the API before it is written to the queue.
#
# ADD TO THIS LIST FREELY. That is the intended way to grow the channel: the
# filter below throws out anything whose translation is too long for a Short,
# so a bad addition costs nothing but a line of output.
AYAT = [
    # with hardship comes ease
    "94:5", "94:6", "94:7", "94:8",
    "93:3", "93:4", "93:5", "93:6", "93:7", "93:8", "93:9", "93:10", "93:11",
    # remembrance, patience, nearness, dua
    "2:45", "2:152", "2:153", "2:155", "2:156", "2:186", "2:216", "2:286",
    "3:139", "3:159", "3:160", "3:185", "3:200",
    "8:46", "12:87", "13:11", "13:28", "14:7", "20:114", "21:83", "21:87",
    "29:2", "29:69", "39:53", "40:60", "42:30", "47:7", "64:11", "65:2",
    "65:3", "94:1",
    # how a person deals with people
    "4:36", "4:58", "4:86", "5:2", "5:8",
    "16:90", "16:97", "16:125", "16:128",
    "17:23", "17:24", "17:26", "17:36", "17:37", "17:53", "17:110",
    "24:22", "25:63", "25:72", "25:74",
    "28:77", "30:21", "31:17", "31:18", "31:19",
    "41:34", "42:37", "42:38", "42:43", "49:6", "49:10", "49:11", "49:12",
    "49:13", "58:11", "59:9",
    # what a person owes their own self
    "2:110", "2:261", "2:268", "2:277", "3:92", "3:110", "3:134",
    "6:162", "7:31", "7:55", "7:56", "7:199", "9:105", "9:119",
    "10:57", "11:6", "11:114", "18:23", "18:24", "18:46", "18:110",
    "20:124", "23:1", "23:2", "23:3", "26:80", "27:62",
    "29:45", "29:64", "31:16", "32:16", "33:21", "33:41", "33:70", "33:71",
    "35:5", "35:15", "36:82", "39:9", "39:10", "43:32", "45:13",
    "51:56", "53:31", "53:38", "53:39", "55:13", "55:60",
    "57:4", "57:16", "57:20", "59:18", "61:2", "61:3", "62:10", "63:9",
    "64:15", "64:16", "65:7", "66:6", "67:2", "67:15", "68:4",
    "76:3", "76:8", "79:40", "79:41",
    "87:14", "87:16", "87:17", "89:27", "89:28", "89:29", "89:30",
    "90:4", "91:9", "91:10", "92:5", "92:6", "92:7",
    "95:4", "96:1", "99:7", "99:8", "100:6", "102:1", "102:2",
    "103:1", "103:2", "103:3", "104:1", "107:4", "107:5", "107:6", "107:7",
    "109:6", "110:3", "112:1", "112:2", "112:3", "112:4",
    # ── added 2026-09-05 — same rule, more of it ─────────────────────────────
    # sabr: the verses that name difficulty without promising it away
    "2:157", "2:250", "3:146", "3:186", "6:34", "10:109", "11:115",
    "12:18", "12:83", "12:90", "14:12", "16:42", "16:96", "16:127",
    "18:28", "19:65", "20:130", "22:35", "23:111", "25:20", "28:80",
    "30:60", "31:22", "38:44", "40:55", "40:77", "41:35",
    "42:33", "46:35", "50:39", "52:48", "68:48",
    "74:7", "90:17",
    # shukr, and noticing what was already given
    "2:172", "7:10", "16:14", "16:18", "16:78", "16:114", "27:19",
    "27:40", "31:12", "31:14", "34:13", "39:66", "46:15", "55:78",
    "56:74", "76:9", "108:2",
    # dua, and turning back
    "2:127", "2:200", "2:201", "3:8", "3:16", "3:38", "3:147",
    "3:191", "3:193", "3:194", "7:23", "7:151", "10:10", "14:40",
    "14:41", "18:10", "20:25", "20:26", "20:27", "20:28", "21:89",
    "23:97", "23:98", "23:109", "23:118", "25:65", "26:83", "28:24",
    "37:100", "40:7", "59:10", "66:8", "66:11", "71:28",
    # tauba and mercy — never a ruling, only the door being open
    "2:222", "3:31", "3:135", "4:110", "5:39", "7:201", "8:29",
    "9:104", "11:3", "11:90", "13:29", "19:76", "20:132", "25:70",
    "25:71", "35:29", "39:54", "41:30", "42:25", "57:7", "57:11",
    "71:10", "71:11", "71:12", "73:8", "87:15", "88:17", "88:18",
    "88:19", "88:20", "91:7", "91:8", "92:12", "96:4", "96:5", "96:14",
    # people: speech, promises, forgiveness, the tongue
    "2:83", "2:263", "2:264", "2:267", "2:271", "2:273", "2:280",
    "3:104", "3:133", "4:19", "4:135", "4:148", "4:149", "5:9",
    "6:151", "6:152", "7:29", "7:85", "7:180", "9:71", "11:85",
    "11:88", "12:92", "14:24", "15:88", "16:91", "17:34",
    "17:35", "20:44", "23:96", "24:27", "24:30", "26:183", "28:26",
    "28:83", "31:15", "33:58", "39:18", "41:33", "42:40", "45:14",
    "49:1", "49:2", "60:8",
    "70:24", "70:25", "74:6", "83:1", "83:2", "83:3", "89:17",
    "89:18", "89:19", "89:20", "90:13", "90:14", "90:15", "90:16",
    "92:18", "92:19", "92:20", "104:2", "104:3", "107:1", "107:2",
    "107:3",
    # rizq: the anxiety this audience actually carries
    "3:27", "3:37", "5:88", "8:26", "16:71", "17:30", "17:31",
    "24:38", "28:60", "29:17", "29:60", "30:37", "34:36", "34:39",
    "35:3", "39:52", "42:12", "42:19", "42:27", "45:5", "51:22",
    "51:58", "62:11", "106:3", "106:4",
    # ilm, and looking at what is in front of you
    "2:269", "3:190", "6:50", "12:76", "13:19", "16:43", "22:46",
    "29:20", "29:43", "30:8", "35:28", "38:29", "47:24", "50:37",
    "59:21",
]


def _load() -> dict:
    if os.path.exists(ISLAMIC_QUEUE_FILE):
        with open(ISLAMIC_QUEUE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _posted_keys() -> set[str]:
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError:
            return set()
    return {e.get("topic", "") for e in entries if e.get("results")}


def show() -> int:
    queue = _load()
    done = _posted_keys()
    for pillar, entries in queue.items():
        if pillar.startswith("_"):
            continue
        left = [e for e in entries
                if f"{'quran' if e.get('quran') else 'hadith'} "
                   f"{e.get('quran') or e.get('hadith')}" not in done]
        print(f"  {pillar}: {len(left)} left of {len(entries)}")
    return 0


def gather_quran() -> list[dict]:
    kept = []
    for ref in AYAT:
        try:
            item = sources.ayah(ref)
        except Exception as e:                       # noqa: BLE001
            print(f"  {ref}: skipped — {str(e)[:90]}")
            continue
        words = len(item["urdu"].split())
        if words > MAX_AYAH_WORDS:
            print(f"  {ref}: skipped — translation is {words} words, too long "
                  f"for a Short")
            continue
        kept.append({"quran": ref, "_ur": item["urdu"][:60]})
    return kept


def gather_hadith() -> list[dict]:
    kept = []
    for page in range(1, HADEETH_PAGES + 1):
        try:
            ids = sources.hadith_ids(HADEETH_CATEGORY, PER_PAGE, page)
        except Exception as e:                       # noqa: BLE001
            print(f"  category {HADEETH_CATEGORY} page {page}: {str(e)[:90]}")
            break
        if not ids:
            break
        for hid in ids:
            try:
                item = sources.hadith(hid)
            except Exception:                        # noqa: BLE001
                # Almost always the grade check refusing it. Silent: this loop
                # looks at hundreds and the refusals are the normal case.
                continue
            words = len(item["urdu"].split())
            if not (6 <= words <= MAX_HADITH_WORDS):
                continue
            if not item["explanation"]:
                # The writer is required to stay inside the published
                # explanation. With no explanation there is nothing to stay
                # inside, and the model would be left to interpret a hadith on
                # its own — which is the thing this whole design avoids.
                continue
            kept.append({"hadith": hid, "_ur": item["urdu"][:60]})
    return kept


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true",
                    help="print what is in the queue and stop")
    args = ap.parse_args()
    if args.show:
        return show()

    queue = _load()
    have_q = {e["quran"] for e in queue.get("quran", []) if e.get("quran")}
    have_h = {e["hadith"] for e in queue.get("hadith", []) if e.get("hadith")}

    print("Checking the verses against alquran.cloud")
    quran = [e for e in gather_quran() if e["quran"] not in have_q]
    print(f"  {len(quran)} new")

    print("Reading HadeethEnc — this walks a few hundred entries")
    hadith = [e for e in gather_hadith() if e["hadith"] not in have_h]
    print(f"  {len(hadith)} new")

    queue.setdefault("_comment", (
        "The scripture channel's input queue. Two pillars, alternating day by "
        "day. An entry is {\"quran\": \"surah:ayah\"} or {\"hadith\": \"<id>\"} "
        "— the id is HadeethEnc's. `_ur` is only there so this file can be "
        "read by eye; nothing uses it. Top it up with build_queue.py, which "
        "refuses anything too long for a Short or graded below hasan."))
    queue.setdefault("quran", []).extend(quran)
    queue.setdefault("hadith", []).extend(hadith)

    os.makedirs(os.path.dirname(ISLAMIC_QUEUE_FILE), exist_ok=True)
    with open(ISLAMIC_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"{ISLAMIC_QUEUE_FILE}: {len(queue['quran'])} verses, "
          f"{len(queue['hadith'])} hadiths — "
          f"{len(queue['quran']) + len(queue['hadith'])} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
