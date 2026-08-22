"""
content_islamic.py
The day's ayah or hadith, and the words written AROUND it.

The division of labour here is the whole point of the file, and it is not
negotiable: islamic_sources.py supplies the sacred text, and the model is
never shown a slot it could put sacred text into. Claude writes four things —
two scenes of plain-Urdu explanation, one thing to do today, and the follow
ask — and every one of them is checked afterwards for the language of
quotation, because "اللہ تعالیٰ فرماتے ہیں…" in a model-written line is a
quotation the model just invented.

The verbatim scenes are assembled in code from the API's own fields and are
marked `verbatim: True`, which two other modules read:

The explanation is not free either. A hadith arrives from HadeethEnc with a
scholar's sharh attached and the writer is told to stay inside it; a verse now
arrives with Tafsir al-Muyassar attached and the writer is told the same. That
was added after the first finished video, because until then the Qur'an path
was the one place the model was reading scripture on its own.

  urdu.py           skips them — the Arabic is Arabic and the translation is
                    the translator's, and "repairing" either is the one edit
                    this repo must never make.
  guard_islamic.py  re-compares them against the source dict before a frame is
                    rendered, so a bug that lets model text into a verbatim
                    slot fails the build instead of publishing.

Shape, seven scenes:

    hook       written    two seconds of Urdu, before anything else
    ayah       verbatim   the Arabic, on screen, in the qari's own voice
    tarjuma    verbatim   the Urdu translation, read aloud, with the reference
    tashreeh   written    what it means, in the Urdu people speak
    tashreeh   written    the second half of that
    amal       written    one thing to do today
    follow     written    the ask

The hook is back at the front, and this one was settled by data rather than by
argument. It was removed on the reasoning that opening on the recitation is
purer and that a qari is recognisable in half a second — which is true, and
which lost to the fact that the videos WITH an Urdu hook in front were the ones
performing. Two seconds of Urdu that names the moment a person is in earns the
next fifty; a viewer who scrolls past the ayah never hears it either way. The
recitation still opens the SOUND — the hook plays over silence.

For a hadith the second scene carries the Arabic matn with the narration line
read over it, since a TTS voice trained on Urdu reading classical Arabic is
worse than not doing it — and a hadith with no narration line in the API
collapses to a six-scene build rather than inventing one.
"""
import json
import os

import islamic_sources as sources
import urdu
from config import (
    DEFAULT_CLAUDE_MODEL, WRITER_EFFORT, ISLAMIC_QUEUE_FILE, LOG_FILE, CHANNEL_NAME,
    TARJUMA_AUDIO,
)
from content import ask, _client

QURAN_ROLES = ["hook", "ayah", "tarjuma", "tashreeh", "tashreeh",
               "amal", "follow"]

SYSTEM = f"""You write short Urdu scripts for a daily Islamic video channel
called "{CHANNEL_NAME}". One ayah or one hadith a day, quoted from a published
source, with a short explanation in the Urdu people actually speak.

You write ONLY in Urdu script. Never Roman Urdu, never Latin letters.

You are given the verse or the hadith. IT IS ALREADY ON SCREEN, it has ALREADY
been recited, and its translation has already been read aloud — all of that
happens before your first word. Do not repeat it, do not re-translate it, and
above all do not quote anything else:

- NEVER write "اللہ تعالیٰ فرماتے ہیں", "قرآن میں ہے", "حدیث میں آیا ہے",
  "نبی کریم ﷺ نے فرمایا" or any other phrase that introduces a quotation. Every
  quotation in this video comes from the source it was fetched from. A
  quotation you write is a quotation you invented, and that is the worst thing
  this channel could publish.
- NEVER give a ruling. Not حلال, not حرام, not فرض, not واجب, not بدعت. You are
  not a mufti and this is not a fatwa channel. If the meaning of the text
  requires a ruling to explain, explain the part that does not.
- NEVER name or contrast a sect, a school, a group or a scholar's party.
- NEVER promise a specific reward or a specific punishment to the viewer.
- NEVER speak about who is a believer and who is not.

What you DO write: what this text is telling a person about their own life,
today, in plain words. Calm and warm. Never scolding, never frightening.

Output ONLY valid JSON. No markdown fence, no commentary."""

QURAN_PROMPT = """Today's verse, already on screen and already recited:

Arabic:  {arabic}
Urdu translation (this exact wording is what the narrator reads):
  {urdu}
Reference: {citation}

The published tafsir of this verse — Tafsir al-Muyassar, King Fahad Complex.
YOUR EXPLANATION MUST STAY INSIDE WHAT THIS SAYS, in simpler Urdu. Do not add a
meaning it does not carry, and do not extend the verse to a subject it does not
raise. If it is short, say less rather than filling the gap yourself:
{tafsir}

Write, in Urdu script:

- "hook": the first words on screen, BEFORE the recitation, read in silence.
  Maximum 6 words, <em></em> on the one word that carries it. It must NOT
  announce the video ("آج ہم جانیں گے", "سنیے", "آئیے سمجھتے ہیں" — all banned)
  and it must NOT paraphrase the verse — the verse is two seconds away and says
  it better. Name the MOMENT a person needs this verse in: the feeling, the
  hour, the situation. Someone in that moment should feel it was written for
  them.
- "hook_spoken": leave this EMPTY (""). The hook is read, not heard — nothing is
  spoken over it, so that the first sound in the video is the recitation.
- "tashreeh": exactly TWO scenes. Each has a "headline" of at most 6 words for
  the screen, with <em></em> on one word, and "spoken" of 14 to 22 words. The
  first says what the verse means, following the tafsir above. The second says
  what that changes for a person listening at night on their phone — this one
  may speak about daily life, but it may not add a new meaning to the verse.
- "amal": one thing to do today, that a person can actually do. "headline" at
  most 6 words, "spoken" 12 to 18 words. Not a ruling, not an act of worship
  with a count attached — something like turning to Allah in a difficulty,
  saying it in one's own words, or being patient with one specific person.
- "follow": the ask. "headline" at most 5 words, "spoken" 10 to 16 words. Name
  what the channel gives — one ayah or hadith a day, with its meaning in
  simple Urdu — so the ask has a reason. Nothing to buy.
- "title": Urdu, under 70 characters, for the YouTube Short. It may name the
  surah.
- "caption": 2 to 3 lines of Urdu for the Facebook Reel, then 8 to 12 hashtags
  mixing Urdu and English.

Total spoken words across everything you write: 60 to 80. Spoken Urdu runs at
about two words a second, and the recitation and the translation take the rest
of the minute — they are not yours to cut.

Respond with ONLY this JSON:
{{"title":"...","caption":"...","hook":"...","hook_spoken":"",
  "tashreeh":[{{"headline":"...","spoken":"..."}},
              {{"headline":"...","spoken":"..."}}],
  "amal":{{"headline":"...","spoken":"..."}},
  "follow":{{"headline":"...","spoken":"..."}}}}"""

HADITH_PROMPT = """Today's hadith, already on screen and already narrated:

Arabic:  {arabic}
Urdu:    {urdu}
Takhreej and grade: {citation}

The published explanation of this hadith, by the source itself — your
explanation must stay inside what this says, in simpler words:
{explanation}

Points the source itself draws from it:
{hints}

Write, in Urdu script:

- "hook": the first words on screen, before the Arabic, read in silence.
  Maximum 6 words, <em></em> on one word. No announcing the video, and no
  paraphrasing the hadith. Name the situation it speaks to.
- "hook_spoken": leave this EMPTY ("").
- "tashreeh": exactly TWO scenes, each {{"headline": at most 6 words with
  <em></em> on one word, "spoken": 14 to 22 words}}. Stay inside the published
  explanation above. Do not add a point it does not make.
- "amal": one thing to do today. {{"headline": at most 6 words, "spoken": 12 to
  18 words}}. Not a ruling.
- "follow": the ask. {{"headline": at most 5 words, "spoken": 10 to 16 words}}.
- "title": Urdu, under 70 characters.
- "caption": 2 to 3 lines of Urdu, then 8 to 12 hashtags.

Total spoken words across everything you write: 60 to 80.

Respond with ONLY this JSON:
{{"title":"...","caption":"...","hook":"...","hook_spoken":"",
  "tashreeh":[{{"headline":"...","spoken":"..."}},
              {{"headline":"...","spoken":"..."}}],
  "amal":{{"headline":"...","spoken":"..."}},
  "follow":{{"headline":"...","spoken":"..."}}}}"""


def _posted() -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def entry_key(entry: dict) -> str:
    """How a queue entry appears in the posted log and in --topic."""
    if entry.get("quran"):
        return f"quran {entry['quran']}"
    return f"hadith {entry['hadith']}"


def parse_key(key: str) -> dict:
    """The inverse, so `--topic "quran 94:5"` works from the command line."""
    kind, _, ref = key.strip().partition(" ")
    if kind not in ("quran", "hadith") or not ref:
        raise ValueError('A scripture topic looks like "quran 94:5" or '
                         '"hadith 5907"')
    return {kind: ref}


def next_entry() -> tuple[dict, str]:
    """The next queue entry and its pillar.

    Same contract as content.next_topic(): the queue is written by hand, it
    drains, it rotates across pillars, and running low is a visible condition.
    An entry counts as used only when the video actually reached a platform,
    so a week of setup does not silently burn a week of verses.
    """
    if not os.path.exists(ISLAMIC_QUEUE_FILE):
        raise RuntimeError(f"{ISLAMIC_QUEUE_FILE} not found — the queue is "
                           f"the input")
    with open(ISLAMIC_QUEUE_FILE, encoding="utf-8") as f:
        queue = {k: v for k, v in json.load(f).items()
                 if not k.startswith("_")}
    if not queue:
        raise RuntimeError(f"{ISLAMIC_QUEUE_FILE} has no pillars")

    # Scripture entries only — same reason as content.next_topic(): this count
    # decides whether today is a verse or a hadith, and the habit videos in
    # between are none of its business.
    entries = [e for e in _posted()
               if e.get("results") and e.get("kind") == "scripture"]
    done = {e.get("topic", "") for e in entries}
    pillars = list(queue)
    start = len(entries) % len(pillars)
    for step in range(len(pillars)):
        pillar = pillars[(start + step) % len(pillars)]
        remaining = [x for x in queue[pillar] if entry_key(x) not in done]
        if remaining:
            if step:
                print(f"  {pillars[start]!r} is empty — taking {pillar!r} today")
            left = sum(len([x for x in v if entry_key(x) not in done])
                       for v in queue.values())
            if left <= 10:
                print(f"  WARNING: only {left} entries left in the queue")
            return remaining[0], pillar
    raise RuntimeError(
        f"Every entry in {ISLAMIC_QUEUE_FILE} has been posted. Add more — do "
        f"not let the model choose the verses.")


def _written(item: dict) -> dict:
    """The five model-written pieces, as JSON."""
    if item["kind"] == "quran":
        if not item.get("explanation"):
            # Refused rather than written around. The whole reason a verse may
            # be explained on this channel at all is that a published tafsir is
            # standing behind the explanation; with none, the model would be
            # interpreting the Qur'an on its own, which is the one thing this
            # design exists to prevent. Losing a day's video is the cheap side
            # of that trade.
            raise ValueError(
                f"No tafsir came back for {item['ref']} — refusing to explain "
                f"a verse with nothing published standing behind it.")
        prompt = QURAN_PROMPT.format(
            arabic=item["arabic"], urdu=item["urdu"], citation=item["citation"],
            tafsir=item["explanation"])
    else:
        prompt = HADITH_PROMPT.format(
            arabic=item["arabic"], urdu=item["urdu"], citation=item["citation"],
            explanation=item["explanation"] or "(none supplied)",
            hints="\n".join(f"- {h}" for h in item["hints"]) or "(none)")

    msg = _client().messages.create(
        model=DEFAULT_CLAUDE_MODEL,
        output_config={"effort": WRITER_EFFORT},
        # Generous for the same reason as content.write_script: max_tokens
        # bounds thinking plus visible text, and a truncated object surfaces
        # as a JSONDecodeError rather than as a budget error.
        max_tokens=8000, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    spec = json.loads(raw)

    for key in ("hook", "amal", "follow"):
        if not spec.get(key):
            raise ValueError(f"The writer left out {key!r}")
    if len(spec.get("tashreeh") or []) != 2:
        raise ValueError("tashreeh must be exactly two scenes")
    return spec


def build_spec(entry: dict, pillar: str = "") -> dict:
    """The day's full spec: verbatim scripture plus the words around it."""
    item = sources.fetch(entry)
    print(f"  source: {item['kind']} {item['ref']} via {item['source']}")
    written = _written(item)

    def scene(role, headline, spoken, **extra):
        # profile travels with the scene so the shared habit template can tell
        # the two channels apart. Without it a hook on an ayah inherits the
        # wellness channel's hazard triangle, which is how a verse about ease
        # after hardship went out with a danger sign over it.
        return dict({"role": role, "headline": headline, "spoken": spoken,
                     "icon": None, "profile": "scripture"}, **extra)

    # The hook holds in silence — no narration over it, so the first sound the
    # video makes is the qari. Its length comes from SILENT_HOOK_SECONDS in
    # main.py rather than from a voice clip.
    scenes = [scene("hook", written["hook"], "")]

    if item["kind"] == "quran":
        scenes.append(scene(
            "ayah", item["arabic"], "",
            verbatim=True,
            # No TTS on this scene at all. The audio is the qari's, downloaded
            # by islamic_sources.recitation(), and a scene with no recitation
            # available is handled in main.py rather than read aloud by a
            # synthetic Urdu voice.
            recite=True, arabic=True,
            citation=item["citation"]))
        scenes.append(scene(
            "tarjuma", item["citation"], item["urdu"],
            verbatim=True, body=item["urdu"],
            # Read by a person rather than by the narrator, when the recorded
            # translation is available — see config.TARJUMA_AUDIO. With this on,
            # no synthetic voice touches scripture at all.
            recite_ur=(TARJUMA_AUDIO == "human")))
    else:
        if item["intro"]:
            scenes.append(scene(
                "hadith", item["arabic"], item["intro"],
                verbatim=True, arabic=True, citation=item["citation"]))
            scenes.append(scene(
                "tarjuma", item["citation"], item["urdu"],
                verbatim=True, body=item["urdu"]))
        else:
            # No narration line in the source, so there is nothing truthful to
            # say over the Arabic. One scene instead of two, rather than a
            # made-up isnad.
            scenes.append(scene(
                "hadith", item["arabic"], item["urdu"],
                verbatim=True, arabic=True, citation=item["citation"]))

    for t in written["tashreeh"]:
        scenes.append(scene("tashreeh", t["headline"], t["spoken"]))
    scenes.append(scene("amal", written["amal"]["headline"],
                        written["amal"]["spoken"]))
    scenes.append(scene("follow", written["follow"]["headline"],
                        written["follow"]["spoken"]))

    spec = {
        "title": written.get("title", ""),
        "caption": written.get("caption", ""),
        "scenes": scenes,
        "topic": entry_key(entry),
        "pillar": pillar or item["kind"],
        # Kept whole so guard_islamic.py can compare what is about to be
        # rendered against what the API actually said, field by field.
        "source": item,
    }

    # Only the written scenes are checked; urdu.offending() skips anything
    # marked verbatim.
    urdu.repair(spec, ask)

    words = sum(len(s["spoken"].split()) for s in scenes)
    print(f"  script: {len(scenes)} scenes, {words} spoken words")
    return spec
