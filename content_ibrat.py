# -*- coding: utf-8 -*-
"""
content_ibrat.py
The story kind: one moment, two choices, and what each one costs.

WHY THIS EXISTS
  Naseem's ask, and it is a genuinely different video from the other three.
  The scripture kind puts a verse on screen and explains it; this one shows a
  person in an ordinary Pakistani afternoon — a shopkeeper's change, a
  neighbour's request, a child's broken cup — takes the same moment twice, and
  lets both versions run to their ends. The verse arrives last, over the story
  it has just been watched happening.

THE SHAPE, and why it is this one

    neki           the small right thing, done quietly
    natija_neki    what it opens up in this world
    gunah          the SAME moment, the other choice
    natija_gunah   what that closes in this world
    akhirat        the turn: this world was not the whole account
    tarjuma        VERBATIM — the day's verse, with its reference
    follow         the ask

  The two halves must be the same situation, not two situations. A video that
  shows a good man and then a different bad man is a fable about two strangers;
  a video that runs one person's afternoon twice is about the viewer, who
  stands in that moment about weekly.

WHAT THE MODEL IS AND IS NOT ALLOWED TO WRITE
  The story is the model's. Nothing else is, and the line sits where the rest
  of this repo puts it:

  * The closing verse is fetched verbatim by islamic_sources.py and checked
    against the source by guard_ibrat before a frame is rendered. The model is
    never shown a slot it could put scripture into — and, the part specific to
    this kind, it does not CHOOSE the verse either. The pairing of a situation
    with a verse lives in data/ibrat_queue.json and is written by hand. A model
    asked to find a verse that fits a story it has just written will always
    find one that sounds like it fits, and on this channel that is not a
    quality problem, it is the entire risk.
  * The story is a MADE-UP EXAMPLE and is never told as something that
    happened. No prophet, no companion, no historical figure, no named person
    at all — narrating a religious account is quoting by another route, and it
    would be a model's version of one. guard_ibrat refuses the language of "a
    true incident" outright.
  * The akhirat scene says a person will be asked. It does not say where
    anybody ends up. guard_islamic already refuses that, and this format walks
    straight at it, so the prompt says it twice.
"""
import json
import os

import islamic_sources as sources
import urdu
from config import (
    DEFAULT_CLAUDE_MODEL, WRITER_EFFORT, CHANNEL_NAME, TARJUMA_AUDIO,
)
from content import ask, _client, _posted

IBRAT_QUEUE_FILE = os.environ.get("IBRAT_QUEUE_FILE") or "data/ibrat_queue.json"

# The story's own scenes, in order. The verbatim scene and the ask are added in
# build_spec and are not the writer's to move.
STORY_ROLES = ["neki", "natija_neki", "gunah", "natija_gunah", "akhirat"]

# Which half of the argument a scene belongs to, carried into the frame as
# colour. Green is this channel's "here is what to do" and gold its "here is
# the problem" — templates/scene.py has used them that way since the first
# video, so an ibrat video is legible as itself before a word is read.
TONE = {
    "neki": "accent_2", "natija_neki": "accent_2",
    "gunah": "accent", "natija_gunah": "accent", "akhirat": "accent",
    "follow": "accent_2",
}

# Total spoken words the STORY gets. The rest of the minute is not the writer's:
# the translation is read aloud after it, by a person, and its length is set by
# the verse. Measured the way content.py's budget was — spoken Urdu runs at
# about two words a second, so 85 words is 42 seconds of story before a single
# pad, and a 150-character verse adds another eight.
STORY_WORDS = os.environ.get("IBRAT_WORDS") or "65 to 85"

SYSTEM = f"""You write 60-second Urdu short-form video scripts for an Urdu
channel called "{CHANNEL_NAME}".

This one is a STORY. One ordinary person, one ordinary moment, told twice —
once where they do the small right thing, once where they do not — and then
what each version costs. Everyday Pakistan: a shop, a street, a kitchen, a
workplace, a courtyard.

You write ONLY in Urdu script. Never Roman Urdu, never Latin letters. The topic
you are given is typed in Roman Urdu because that is what is convenient to type
into a queue file. It is an instruction to you, not a sample of the writing.

Natural spoken Urdu — the Urdu a person actually speaks, not translated English
and not literary Urdu. Short sentences. Calm and unhurried. Never scolding and
never frightening: a person watching this at night should recognise themselves,
not be shouted at.

THE STORY IS AN EXAMPLE. IT DID NOT HAPPEN. Therefore:
- NEVER present it as a real event. Not "ایک سچا واقعہ", not "ایک واقعہ ہے",
  not "ایسا ہوا تھا". It is a picture of a situation, nothing more.
- NEVER put a prophet, a companion, a saint or any historical religious figure
  in it, and never narrate anything attributed to one. That is quoting by
  another route, and it would be your version of the quotation.
- NEVER name your character. "ایک آدمی", "ایک لڑکی", "دکاندار", "پڑوسی" — a
  role, never a name, and never a real person, family or brand.

WHAT YOU MUST NEVER WRITE, in any scene:
- Any quotation. Not an ayah, not a hadith, not "اللہ تعالیٰ فرماتے ہیں",
  "قرآن میں ہے", "حدیث میں آیا ہے", "نبی کریم ﷺ نے فرمایا". The verse this
  video ends on has already been fetched from a published source and placed in
  the frame for you. A quotation you write is a quotation you invented.
- Any ruling — حلال, حرام, فرض, واجب, بدعت, جائز نہیں. This is not a fatwa
  channel.
- Any sect, school, group or scholar's party.
- Where anybody ends up. Not جنت, not جہنم, not "بخشش ملے گی", not "گناہ معاف
  ہو جائیں گے", not "ستر نیکیاں". You may say that a person will be ASKED, and
  that nothing is lost or forgotten. You may not hand down the verdict.
- Any medical claim, disease, medicine or dose.
- Hashtags or emoji inside a scene.

Output ONLY valid JSON. No markdown fence, no commentary."""

PROMPT = """Today's situation: {topic}

The verse this video ENDS on. It is already fetched and it is already on screen
after your last story scene, with its reference, read aloud. Do not quote it,
do not paraphrase it, and do not mention that a verse is coming. Write the
story so that this verse lands as the thing it was always about:

  {urdu}
  ({citation})

Write these five scenes, in this exact order:

- "neki": the moment, and the small right thing done in it. Quiet and
  unremarkable — nobody is watching and nothing is announced. This is the first
  frame of the video and it has two seconds to stop a scroll, so open ON the
  moment. Do not announce the video: "آج ہم دیکھیں گے", "ایک کہانی سنیے",
  "آئیے سمجھتے ہیں" — all banned.
- "natija_neki": what that opens up, in THIS world. Modest and believable. Not
  wealth, not a transformed life, not a reward with a date on it — something
  small and true: how a person is seen, how they sleep, who trusts them next.
- "gunah": THE SAME MOMENT AGAIN, with the other choice. The same shop, the
  same hour, the same person. This is the whole design of the format — if it
  becomes a different scene about a different person, the video is a fable
  about strangers instead of a mirror. Name what makes the wrong choice
  tempting; it is never stupid, it is always easier.
- "natija_gunah": what that closes, in THIS world. Again small and true — what
  it costs to be the person who did that, not a catastrophe.
- "akhirat": the turn. This world was not the whole account: both versions of
  that afternoon were seen, and both will be asked about. Say that nothing is
  too small to be counted. Do NOT say where anybody goes.

For each scene:
- "headline": the words ON SCREEN. Urdu. Maximum 6 words. Wrap the single most
  important word in <em></em>. It is read, not heard, and it must land alone.
- "spoken": what the narrator SAYS. Urdu. 12 to 18 words. It must NOT be the
  headline read aloud — it carries the detail the headline leaves out.

Also write:
- "follow": the ask. {{"headline": at most 5 words, "spoken": 10 to 16 words}}.
  Name what the channel gives, so the ask has a reason. Nothing to buy.
- "title": Urdu, under 70 characters, for the YouTube Short.
- "caption": 2 to 3 lines of Urdu for the Facebook Reel, then 8 to 12 hashtags
  mixing Urdu and English.

Total spoken words across all six scenes: {words}. This is a hard budget. The
translation is read aloud after your last scene and its length is not yours to
cut, so the story overrunning is the story losing the verse it was written for.

Respond with ONLY this JSON:
{{"title":"...","caption":"...",
  "scenes":[{{"role":"neki","headline":"...","spoken":"..."}},
            {{"role":"natija_neki","headline":"...","spoken":"..."}},
            {{"role":"gunah","headline":"...","spoken":"..."}},
            {{"role":"natija_gunah","headline":"...","spoken":"..."}},
            {{"role":"akhirat","headline":"...","spoken":"..."}}],
  "follow":{{"headline":"...","spoken":"..."}}}}"""


# ------------------------------------------------------------------ the queue

def entry_key(entry: dict) -> str:
    """How an entry appears in the posted log and in --topic.

    The SITUATION, not the verse. Two entries may legitimately close on the
    same ayah — a verse about what a person says covers both a lie and a
    rumour — and keying by the verse would silently retire the second one.
    """
    return entry["topic"]


def entry_ref(entry: dict) -> str:
    """The closing scripture, for a log line."""
    if entry.get("quran"):
        return f"quran {entry['quran']}"
    return f"hadith {entry['hadith']}"


def _queue() -> list[dict]:
    if not os.path.exists(IBRAT_QUEUE_FILE):
        raise RuntimeError(f"{IBRAT_QUEUE_FILE} not found — the queue is the "
                           f"input")
    with open(IBRAT_QUEUE_FILE, encoding="utf-8") as f:
        rows = json.load(f).get("entries") or []
    if not rows:
        raise RuntimeError(f"{IBRAT_QUEUE_FILE} has no entries")
    return rows


def parse_key(key: str) -> dict:
    """`--topic "..."` resolved against the queue, and only against it.

    Deliberately NOT "build a video about whatever this says". An ibrat video
    needs a verse, and the verse is not the model's to choose — so a topic that
    is not in the queue is an instruction to add it there with the verse that
    belongs to it, not a reason to let today's build pick one.
    """
    want = key.strip().lower()
    rows = _queue()
    for row in rows:
        if row["topic"].lower() == want:
            return row
    hits = [r for r in rows if want in r["topic"].lower()]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise ValueError(f"{key!r} matches {len(hits)} entries: "
                         + "; ".join(r["topic"] for r in hits))
    raise ValueError(
        f"No entry in {IBRAT_QUEUE_FILE} for {key!r}. Add it there with the "
        f"verse it closes on — this kind does not let the build choose the "
        f"scripture.")


def next_entry() -> dict:
    """The next unused situation.

    Same contract as the other two queues: written by hand, drained in order,
    running low is a visible condition, and an entry counts as used only when
    the video actually reached a platform — so a week of setup does not
    silently burn a week of situations.
    """
    rows = _queue()
    done = {e.get("topic", "") for e in _posted()
            if e.get("results") and e.get("kind") == "ibrat"}
    remaining = [r for r in rows if entry_key(r) not in done]
    if not remaining:
        raise RuntimeError(
            f"Every situation in {IBRAT_QUEUE_FILE} has been posted. Add more "
            f"— each paired with the verse it closes on, by hand.")
    if len(remaining) <= 5:
        print(f"  WARNING: only {len(remaining)} ibrat situations left")
    return remaining[0]


# ----------------------------------------------------------------- the script

def _written(topic: str, item: dict) -> dict:
    msg = _client().messages.create(
        model=DEFAULT_CLAUDE_MODEL,
        output_config={"effort": WRITER_EFFORT},
        # Generous for the same reason as the other two writers: max_tokens
        # bounds thinking PLUS visible text, and a truncated object surfaces as
        # a JSONDecodeError rather than as a budget error.
        max_tokens=8000, system=SYSTEM,
        messages=[{"role": "user", "content": PROMPT.format(
            topic=topic, urdu=item["urdu"], citation=item["citation"],
            words=STORY_WORDS)}])
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    out = json.loads(raw)

    # Validated here rather than at render time: a malformed script that
    # reaches the renderer fails after the TTS calls have been paid for and
    # spent against the day's quota.
    scenes = out.get("scenes") or []
    if [s.get("role") for s in scenes] != STORY_ROLES:
        raise ValueError("The story came back with the wrong scenes: "
                         f"{[s.get('role') for s in scenes]}")
    for s in scenes + [out.get("follow") or {}]:
        if not (s.get("headline") or "").strip() or \
                not (s.get("spoken") or "").strip():
            raise ValueError(
                f"Scene {s.get('role', 'follow')!r} is missing text")
    return out


def build_spec(entry: dict, pillar: str = "ibrat") -> dict:
    """The day's full spec: the story, then the verse it was written for."""
    item = sources.fetch(entry)
    print(f"  closes on: {item['kind']} {item['ref']} via {item['source']}")
    written = _written(entry["topic"], item)

    def scene(role, headline, spoken, **extra):
        return dict({"role": role, "headline": headline, "spoken": spoken,
                     "icon": None, "profile": "ibrat",
                     "tone": TONE.get(role)}, **extra)

    scenes = [scene(s["role"], s["headline"], s["spoken"])
              for s in written["scenes"]]

    # The verse, verbatim, with its reference on screen — and read by the
    # person who recorded the translation rather than by the channel's
    # narrator, exactly as a scripture day does it. Nothing synthetic touches
    # scripture on this channel, and a story kind is no reason to start.
    scenes.append(scene(
        "tarjuma", item["citation"], item["urdu"],
        # Read by two other modules: guard_ibrat re-checks these fields against
        # `source` before a frame is rendered, and urdu.repair skips them so
        # the translator's wording is never "corrected".
        verbatim=True, body=item["urdu"],
        # The scripture profile, so this one frame renders through the
        # scripture template — rules above and below, the reference beneath,
        # and none of the habit template's icon badge.
        profile="scripture", tone=None,
        recite_ur=(TARJUMA_AUDIO == "human"),
        # The bed is muted under this scene rather than ducked. Ducking is a
        # level decision and this is not one — see main.py's `quiet` list.
        quiet=True))

    scenes.append(scene("follow", written["follow"]["headline"],
                        written["follow"]["spoken"]))

    spec = {
        "title": written.get("title", ""),
        "caption": written.get("caption", ""),
        "scenes": scenes,
        "topic": entry["topic"],
        "pillar": pillar or "ibrat",
        # Kept whole so guard_ibrat can compare what is about to be rendered
        # against what the API actually said, field by field.
        "source": item,
    }

    # Only the written scenes are touched; urdu.offending() skips verbatim.
    urdu.repair(spec, ask)

    words = sum(len(s["spoken"].split())
                for s in scenes if not s.get("verbatim"))
    print(f"  script: {len(scenes)} scenes, {words} spoken words of story")
    return spec
