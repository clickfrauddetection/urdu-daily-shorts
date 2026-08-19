"""
content.py
The day's topic, and the script written for it.

Topics come from a queue file, not from asking the model for an idea. A model
asked daily to "think of a good topic" converges within about two weeks —
it starts rewording the same four ideas, and nobody notices until a viewer
does. `data/topics.json` is filled by hand once, drained one entry a day, and
the queue running low is a visible, fixable condition rather than a silent
decline in quality.

The shape is fixed: hook, problem, cause, three tactics, action, follow. Fixed
because a 60-second video has room for exactly one idea, and because a fixed
shape lets the icon for each role be decided in code rather than invented by
the model — see icons.ROLE_DEFAULT.
"""
import json
import os

import anthropic

import urdu
from config import (
    ANTHROPIC_API_KEY, DEFAULT_CLAUDE_MODEL, NICHE, TOPICS_FILE, LOG_FILE,
    MAX_DURATION,
)
from icons import known as known_icons

ROLES = ["hook", "problem", "cause", "tactic", "tactic", "tactic",
         "action", "follow"]

SYSTEM = """You write 60-second Urdu short-form video scripts. You write in
natural, spoken Urdu — the Urdu a person actually speaks, not translated
English and not literary Urdu. Short sentences. No English loanwords where a
common Urdu word exists.

EVERY word you write goes on screen in URDU SCRIPT. Never Roman Urdu, never
Latin letters. The topic you are given is typed in Roman Urdu because that is
what is convenient to type into a queue file — it is an instruction to you, not
a sample of the writing. Answering in the script the question was asked in is
the single most common failure here, and it produces a video whose subtitles
are Urdu on some scenes and Latin on others.

You are writing for "Sakoon Zindagi", an Urdu channel about sleep, health
and peaceful daily living. The tone is calm and unhurried, never hyped. You may talk about daily routine,
sleep timing, light, water, walking, screen use, meal timing and rest. You must
NEVER: name a disease or diagnosis, claim anything cures or treats anything,
mention any medicine, supplement, dose or quantity, or tell anyone they do not
need a doctor. Say what to DO, never what it will cure.

Output ONLY valid JSON. No markdown fence, no commentary."""

TEMPLATE = """Topic for today: {topic}
Niche: {niche}

Write the script as eight scenes, in this exact order and with these exact
roles: hook, problem, cause, tactic, tactic, tactic, action, follow.

For each scene:
- "headline": the words ON SCREEN. Urdu. Maximum 6 words. Wrap the single most
  important word in <em></em>. This is read, not heard — it must land alone.
- "spoken": what the narrator SAYS. Urdu. 10 to 20 words. It must NOT be the
  headline read aloud — it carries the detail the headline leaves out.
- "icon": one name from this list, whichever genuinely fits: {icons}

Rules:
- The hook is a question or a sharp claim, and it must work with no sound.
- The hook must NOT promise to tell them something. "aaj wajah batate hain",
  "aaj hum seekhenge", "jaaniye" — all banned. Those spend the only two
  seconds you are given announcing that the video exists. Put the claim itself
  in the hook: name the cause, or the number, or the mistake, immediately.
- No scene may open by describing what the video will do. Say the thing.
- The "follow" scene asks once, plainly, and names what they get by
  following. It is not a summary of the video they just watched. The
  channel is called Sakoon Zindagi — sleep, health and peaceful living —
  so say what the next videos will help with, in those terms.
- Each "tactic" is ONE concrete thing to do today, with a when or a how much
  that is about routine and timing, never a medical quantity.
- "action" is the single smallest thing to try tonight.
- "follow" asks for a follow, and names the channel's subject so the ask has a
  reason. It offers nothing to buy.
- Total spoken words across all eight scenes: 95 to 120. This is a hard budget.
  Spoken Urdu runs at roughly two words a second, so 150 words is over a
  minute before a single pause is counted — which is how the first live run
  overran and had to be re-asked.

Also produce:
- "title": Urdu, under 70 characters, for the YouTube Short.
- "caption": 2 to 3 lines of Urdu for the Facebook Reel, then 8 to 12
  hashtags mixing Urdu and English tags.

Respond with ONLY this JSON:
{{"title":"...","caption":"...","scenes":[{{"role":"hook","headline":"...","spoken":"...","icon":"..."}}]}}"""


def _client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask(system: str, user: str, max_tokens: int = 2000) -> str:
    """One short model call, text in and text out.

    Shared with content_islamic.py and handed to urdu.repair(), so the
    transliteration pass does not need its own client or its own key handling.
    """
    msg = _client().messages.create(
        model=DEFAULT_CLAUDE_MODEL, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def _posted() -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def next_topic() -> tuple[str, str]:
    """The next topic and its pillar.

    A niche is either a flat list, or an object of pillar -> topics. The object
    form ROTATES: the pillar is chosen by how many videos this channel has
    already posted, so a broad channel does not run five sleep videos in a row
    and get read — by viewers and by the algorithm — as a sleep channel. Within
    a pillar the order is as written, and anything already in the posted log is
    skipped.
    """
    if not os.path.exists(TOPICS_FILE):
        raise RuntimeError(f"{TOPICS_FILE} not found — the queue is the input")
    with open(TOPICS_FILE, encoding="utf-8") as f:
        queue = json.load(f).get(NICHE)
    if not queue:
        raise RuntimeError(f"{TOPICS_FILE} has no topics for niche {NICHE!r}")

    # A topic counts as used only when the video actually reached a platform.
    # The log records every build, but a build that published nowhere — because
    # no Page is set up yet, or every poster failed — is a rehearsal, and
    # burning a topic for it means a week of setup quietly costs seven topics
    # and produces nothing. Rehearsals repeat today's topic until it lands.
    # Habit videos only. The channel alternates with the scripture build, and
    # counting those here would step the pillar rotation twice a day — the
    # rotation is meant to answer "how many of THESE have I posted".
    # `kind` is absent from entries written before the alternation existed;
    # those were all habit videos.
    entries = [e for e in _posted()
               if e.get("results") and e.get("kind", "habit") == "habit"]
    done = {e.get("topic", "") for e in entries}

    if isinstance(queue, list):
        remaining = [t for t in queue if t not in done]
        if not remaining:
            raise RuntimeError(
                f"Every topic for {NICHE!r} has been posted. Add more to "
                f"{TOPICS_FILE} — do not let the model invent them.")
        if len(remaining) <= 7:
            print(f"  WARNING: only {len(remaining)} topics left for {NICHE!r}")
        return remaining[0], NICHE

    pillars = list(queue)
    start = len(entries) % len(pillars)
    # Walk from the pillar whose turn it is, so an exhausted pillar hands the
    # day to the next one instead of ending the channel.
    for step in range(len(pillars)):
        pillar = pillars[(start + step) % len(pillars)]
        remaining = [t for t in queue[pillar] if t not in done]
        if remaining:
            if step:
                print(f"  {pillars[start]!r} is empty — taking {pillar!r} today")
            left = sum(len([t for t in v if t not in done]) for v in queue.values())
            if left <= 10:
                print(f"  WARNING: only {left} topics left across all pillars")
            return remaining[0], pillar

    raise RuntimeError(
        f"Every topic in every pillar of {NICHE!r} has been posted. Add more "
        f"to {TOPICS_FILE} — do not let the model invent them.")


def write_script(topic: str, pillar: str = "", max_words: int | None = None) -> dict:
    """Ask Claude for the day's script and validate its shape before returning.

    Validated here rather than at render time because a malformed script that
    reaches the renderer fails eight scenes in, after the TTS calls have
    already been paid for and spent against the day's quota.
    """
    msg = _client().messages.create(
        model=DEFAULT_CLAUDE_MODEL,
        # Generous, because max_tokens bounds thinking PLUS visible text on
        # current models — the sibling repo's 2200 truncated the JSON
        # mid-object and surfaced as a JSONDecodeError, not as a budget error.
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": TEMPLATE.format(
            topic=topic, niche=pillar or NICHE, icons=", ".join(known_icons()),
            max_secs=MAX_DURATION) + (
            # Appended only on the re-ask, and it carries a real measurement
            # rather than "make it shorter" — the first attempt already had a
            # word budget and overshot it.
            f"\n\nIMPORTANT: your previous attempt was too long when read "
            f"aloud. Total spoken words across all eight scenes must be at "
            f"most {max_words}. Cut detail, not scenes — all eight roles must "
            f"still be there." if max_words else "")}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

    spec = json.loads(raw)
    scenes = spec.get("scenes") or []
    if [s.get("role") for s in scenes] != ROLES:
        raise ValueError(f"Script has the wrong scene roles: "
                         f"{[s.get('role') for s in scenes]}")
    valid = set(known_icons())
    for s in scenes:
        if not s.get("headline") or not s.get("spoken"):
            raise ValueError(f"Scene {s.get('role')} is missing text")
        # An invented icon name is dropped rather than fatal — the role default
        # is always right, and losing a whole day's video over an icon is not a
        # trade worth making.
        if s.get("icon") not in valid:
            if s.get("icon"):
                print(f"  unknown icon {s['icon']!r} on {s['role']} — "
                      f"using the role default")
            s["icon"] = None

    # After the shape is known to be right, before anything is narrated or
    # rendered: every line that will be spoken or shown has to be in Urdu
    # script. A Roman line is transliterated in one small call rather than
    # costing the day's video — see urdu.py for why this is here and not in
    # the renderer.
    urdu.repair(spec, ask)

    spec["topic"] = topic
    spec["pillar"] = pillar or NICHE
    words = sum(len(s["spoken"].split()) for s in scenes)
    print(f"  script: {len(scenes)} scenes, {words} spoken words")
    return spec
