"""
islamic_sources.py
The Qur'an and the Hadith, fetched verbatim. Never written by a model.

This is the one module in the repo whose output is not allowed to be
paraphrased, shortened, "improved" or regenerated. A wellness channel that
gets a sentence slightly wrong loses a viewer; a channel that puts an invented
ayah or a fabricated hadith on screen under a reference number is doing
something else entirely, and no amount of downstream polish fixes it. So:

  * The Arabic text, the Urdu translation, the reference, the attribution and
    the grade all come from an API and are carried to the frame unchanged.
    content_islamic.py asks Claude only for the hook and for an explanation in
    plain Urdu, and guard_islamic.py re-checks the sacred text against what
    this module returned before a single frame is rendered.
  * A hadith with no grade, or a grade this module does not recognise as
    sound, is refused rather than shipped with the grade line left blank.

Sources, both keyless, both checked live before they were wired in:

  Qur'an   api.alquran.cloud    Arabic (Uthmani) and an Urdu translation in
                                one call, plus a per-ayah recitation mp3 on
                                cdn.islamic.network.
  Hadith   hadeethenc.com       The Association for Multi-lingual Islamic
                                Content's own API. Chosen over the larger
                                fawazahmed0/hadith-api mirror for two reasons
                                that matter here and nowhere else: its entries
                                carry an explicit grade and takhreej field, and
                                they are short enough to read on screen. A full
                                Bukhari entry runs past 200 words with the
                                isnad attached, which is a page, not a Short.

The `islamic-content-sdk` package on PyPI wraps these same sources. It is not
used: it is one more dependency between this repo and two endpoints it can
call in four lines, and a break in it would surface as a failed run with
nothing to fix locally.
"""
import json
import os
import time

import requests

from config import (
    QURAN_AR_EDITION, QURAN_UR_EDITION, QURAN_TAFSIR, QURAN_RECITER,
    QURAN_UR_RECITER, ISLAMIC_CACHE_DIR, HTTP_TIMEOUT, HTTP_RETRIES,
)

QURAN_API = "https://api.alquran.cloud/v1"
HADEETH_API = "https://hadeethenc.com/api/v1"

# Urdu is written with the EXTENDED Arabic-Indic digits, not the ones Arabic
# uses and not Latin ones. A reference line reading "94:5" under a frame of
# Nastaliq is the fastest way to make an Urdu video look machine-made, and it
# is one translate() call to avoid.
UR_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def ur_num(n) -> str:
    return str(n).translate(UR_DIGITS)


# Grades that may go to air, as HadeethEnc spells them. Anything else — most
# of all da'eef and mawdoo' — is refused by hadith() rather than published
# with a grade line nobody reads. "متفق عليه" is an attribution rather than a
# grade, but the API returns it in the grade field for the two Sahihs and it
# is the strongest thing it can say.
SOUND_GRADES = {
    "صحيح", "صحيح لغيره", "حسن", "حسن لغيره", "متفق عليه",
    "صحيح لذاته", "حسن صحيح",
}


class SourceError(RuntimeError):
    """The source could not be reached, or answered with something unusable."""


def _get(url: str, params: dict | None = None):
    """One GET, retried, with the response cached on disk.

    Cached because these texts do not change — the Qur'an least of all — and
    because a daily build that re-fetches the same ayah every run turns a
    provider's bad morning into a lost video. The key carries the full request,
    so a different translation edition is a different file rather than a stale
    hit.
    """
    key = url.replace(HADEETH_API, "h").replace(QURAN_API, "q")
    key += "_" + "_".join(f"{k}-{v}" for k, v in sorted((params or {}).items()))
    key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:120]
    path = os.path.join(ISLAMIC_CACHE_DIR, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass

    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except Exception as e:          # noqa: BLE001 — every failure retries
            last = e
            time.sleep(1.5 * (attempt + 1))
            continue
        os.makedirs(ISLAMIC_CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    raise SourceError(f"{url} failed after {HTTP_RETRIES} tries: {last}")


# --------------------------------------------------------------------- Qur'an

def ayah(ref: str) -> dict:
    """One ayah, by "surah:ayah" — Arabic, Urdu, reference and recitation.

    Both editions come back from a single call, which matters: fetching the
    Arabic and the translation separately leaves room for them to disagree
    about which verse they are, and nothing downstream would catch it.
    """
    # All three in ONE call. Separately, the editions could disagree about
    # which verse they are — and a tafsir of the wrong ayah is worse than no
    # tafsir at all, because it would read as if it belonged.
    data = _get(f"{QURAN_API}/ayah/{ref}/editions/"
                f"{QURAN_AR_EDITION},{QURAN_UR_EDITION},{QURAN_TAFSIR}")
    if not isinstance(data, dict) or data.get("code") != 200:
        raise SourceError(f"alquran.cloud did not return ayah {ref}: {data}")
    by_id = {e["edition"]["identifier"]: e for e in data["data"]}
    ar = by_id.get(QURAN_AR_EDITION)
    ur = by_id.get(QURAN_UR_EDITION)
    if not ar or not ur:
        raise SourceError(f"ayah {ref} came back without both editions")
    if ar["numberInSurah"] != ur["numberInSurah"]:
        raise SourceError(f"ayah {ref}: the two editions disagree on the verse")
    tafsir = by_id.get(QURAN_TAFSIR)
    if tafsir and tafsir["numberInSurah"] != ar["numberInSurah"]:
        raise SourceError(f"ayah {ref}: the tafsir is for a different verse")

    surah = ar["surah"]
    n_surah, n_ayah = surah["number"], ar["numberInSurah"]
    return {
        "kind": "quran",
        "ref": f"{n_surah}:{n_ayah}",
        "surah_no": n_surah,
        "ayah_no": n_ayah,
        # The API's surah name is already in Arabic script, which is what an
        # Urdu frame wants — "سُورَةُ الشَّرۡحِ", not "Ash-Sharh".
        "surah_name": surah["name"],
        "surah_en": surah["englishName"],
        "arabic": ar["text"],
        "urdu": ur["text"],
        # Never shown on screen and never spoken — it is the leash on the
        # writer, nothing else. See config.QURAN_TAFSIR.
        "explanation": (tafsir or {}).get("text", ""),
        "tafsir_name": QURAN_TAFSIR,
        # What actually goes on screen under the ayah.
        "citation": f'{surah["name"]} — {ur_num(n_surah)}:{ur_num(n_ayah)}',
        # The GLOBAL ayah number, not the number within the surah, is what the
        # recitation CDN is keyed by.
        "audio_url": f"https://cdn.islamic.network/quran/audio/128/"
                     f"{QURAN_RECITER}/{ar['number']}.mp3",
        # The same CDN carries recorded READINGS OF TRANSLATIONS, one file per
        # ayah, keyed the same way. ur.khan is Shamshad Ali Khan reading the
        # Jalandhry translation. 64kbps because that is the only bitrate the
        # translation editions are published at.
        "urdu_audio_url": f"https://cdn.islamic.network/quran/audio/64/"
                          f"{QURAN_UR_RECITER}/{ar['number']}.mp3",
        "source": "api.alquran.cloud",
    }


def recitation(item: dict, out_path: str, field: str = "audio_url") -> str | None:
    """Download one recorded reading of this ayah. None if unavailable.

    `field` picks which: "audio_url" is the qari's Arabic, "urdu_audio_url" is
    the recorded reading of the translation.

    None rather than an exception on purpose: these files are the best thing in
    an Islamic short, and they are still not worth losing the day's video to a
    CDN having a bad minute. The caller falls back — to silence under the
    Arabic, and to the channel's own narrator for the Urdu.
    """
    url = item.get(field)
    if not url:
        return None
    if os.path.exists(out_path) and os.path.getsize(out_path) > 2000:
        return out_path
    for attempt in range(HTTP_RETRIES):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            if len(r.content) < 2000:
                raise SourceError(f"{field} for {item['ref']} is empty")
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        except Exception as e:          # noqa: BLE001
            print(f"  recitation {item['ref']}: {str(e)[:120]}")
            time.sleep(1.5 * (attempt + 1))
    return None


# --------------------------------------------------------------------- Hadith

def hadith(hadeeth_id: str | int, language: str = "ur") -> dict:
    """One hadith from HadeethEnc, with its grade and takhreej attached."""
    data = _get(f"{HADEETH_API}/hadeeths/one/",
                {"language": language, "id": str(hadeeth_id)})
    if not isinstance(data, dict) or not data.get("hadeeth"):
        raise SourceError(f"HadeethEnc returned nothing for id {hadeeth_id}")

    grade = (data.get("grade") or "").strip()
    if grade not in SOUND_GRADES:
        raise SourceError(
            f"hadith {hadeeth_id} is graded {grade!r}, which is not in "
            f"islamic_sources.SOUND_GRADES — refusing to publish it")

    intro = (data.get("hadeeth_intro") or "").strip()
    body = (data.get("hadeeth") or "").strip()
    # The intro is the narration line ("ابو موسیٰ اشعری رضی اللہ عنہ سے روایت
    # ہے کہ…"). It is part of the hadith and is kept, but it is returned
    # separately so the frame can carry it in a smaller line above the matn
    # rather than burying the words of the Prophet (ﷺ) inside it.
    if intro and body.startswith(intro):
        body = body[len(intro):].strip()

    return {
        "kind": "hadith",
        "ref": str(hadeeth_id),
        "intro": intro,
        "urdu": body,
        "arabic": (data.get("hadeeth_ar") or "").strip(),
        "attribution": (data.get("attribution") or "").strip(),
        "grade": grade,
        # HadeethEnc's own sharh and fawaid, in Urdu. These are what the model
        # is given to explain FROM, so what ends up on screen is a
        # simplification of a scholar's words rather than the model's own
        # reading of a hadith.
        "explanation": (data.get("explanation") or "").strip(),
        "hints": [h.strip() for h in (data.get("hints") or []) if h.strip()],
        "citation": " — ".join(x for x in
                               ((data.get("attribution") or "").strip(), grade)
                               if x),
        "source": "hadeethenc.com",
    }


def hadith_ids(category_id: str | int, per_page: int = 25,
               page: int = 1, language: str = "ur") -> list[str]:
    """The ids in one HadeethEnc category — how the queue file gets filled."""
    data = _get(f"{HADEETH_API}/hadeeths/list/",
                {"language": language, "category_id": str(category_id),
                 "page": str(page), "per_page": str(per_page)})
    rows = data.get("data") if isinstance(data, dict) else data
    return [str(r["id"]) for r in (rows or []) if r.get("id")]


def categories(language: str = "ur") -> list[dict]:
    """Top-level HadeethEnc categories, for filling the queue by subject."""
    data = _get(f"{HADEETH_API}/categories/list/", {"language": language})
    return [{"id": c["id"], "title": c["title"],
             "count": int(c.get("hadeeths_count") or 0),
             "parent": c.get("parent_id")}
            for c in (data or [])]


def fetch(entry: dict) -> dict:
    """Resolve one queue entry — {"quran": "94:5"} or {"hadith": "5907"}."""
    if entry.get("quran"):
        return ayah(str(entry["quran"]))
    if entry.get("hadith"):
        return hadith(entry["hadith"])
    raise SourceError(
        f"queue entry has neither a quran nor a hadith key: {entry}")
