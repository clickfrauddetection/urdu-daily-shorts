"""
urdu.py
Is this line actually in Urdu script, and if not, what do we do about it.

This exists because of a bug that shipped: subtitles that were Urdu on some
scenes and Roman Urdu on others, in the same video. The cause is not the
renderer — templates/scene.py already detects the script per line and lays
Latin text out left-to-right so it degrades to off-brand rather than to
visually reversed nonsense. The cause is upstream: data/topics.json is written
in Roman Urdu, because that is what is comfortable to type, and a model handed
"raat ko bistar par phone dekhne se neend kyun der se aati hai" will now and
then answer in the script the question was asked in. Nothing between the model
and the frame ever checked.

So the check lives here, one implementation, used by both writers. A line that
comes back in Latin letters is repaired — transliterated into Urdu script by
the same model, in one small call, naming only the lines that failed — and the
video is not lost over it. A line that is still Latin after the repair is a
hard failure, because at that point something is wrong with the writer and
shipping a mixed-script video is exactly what this module was added to stop.
"""
import json
import re

# Arabic, Arabic Supplement, Extended-A, and the presentation forms. Urdu's
# own letters (ٹ ڈ ڑ ں ہ ھ ے) all live in the base Arabic block.
_ARABIC = re.compile(
    r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")
# Left in place deliberately: a hashtag block is expected to mix scripts, and
# so is a channel name. Only the words that will be READ are policed.
_HASH = re.compile(r"#\S+")
# And the markup is not text. Every headline carries <em></em> around its key
# word — four Latin letters that a six-word Urdu headline cannot outvote. The
# first test of this module flagged five perfectly good Urdu headlines for it.
_MARKUP = re.compile(r"<[^>]*>")


def arabic_ratio(text: str) -> float:
    """Share of the letters in `text` that are Arabic-script. 1.0 is pure Urdu."""
    text = _HASH.sub(" ", _MARKUP.sub(" ", text or ""))
    ar = len(_ARABIC.findall(text))
    la = len(_LATIN.findall(text))
    if not ar and not la:
        return 1.0          # digits and punctuation only — nothing to judge
    return ar / (ar + la)


def is_urdu(text: str, min_ratio: float = 0.85) -> bool:
    """True when the line reads as Urdu.

    Not 1.0: a stray "AM", a brand name, or "WiFi" inside an otherwise Urdu
    sentence is a style question, not the bug this catches. Roman Urdu scores
    at or near zero, so the two cases are nowhere near each other and the
    exact threshold does not need to be argued about.
    """
    return arabic_ratio(text) >= min_ratio


# Every field of a spec whose text is READ ALOUD or shown as type, with the
# path used to report it. `caption` is checked at a lower bar because its
# hashtag block is legitimately half English.
def offending(spec: dict, min_ratio: float = 0.85) -> list[tuple[str, str]]:
    """The (path, text) pairs that are not in Urdu script."""
    bad = []
    for key, floor in (("title", min_ratio), ("caption", 0.55)):
        text = spec.get(key) or ""
        if text and not is_urdu(text, floor):
            bad.append((key, text))
    for i, scene in enumerate(spec.get("scenes") or []):
        # Verbatim scripture is never touched. It is Arabic or it is the
        # translation exactly as the API returned it, and "repairing" it is
        # the one thing this module must never do.
        if scene.get("verbatim"):
            continue
        for key in ("headline", "spoken"):
            text = scene.get(key) or ""
            if text and not is_urdu(text, min_ratio):
                bad.append((f"scenes[{i}].{key}", text))
    return bad


def apply(spec: dict, path: str, value: str) -> None:
    """Write a repaired line back to the place `offending()` found it."""
    m = re.fullmatch(r"scenes\[(\d+)\]\.(\w+)", path)
    if m:
        spec["scenes"][int(m.group(1))][m.group(2)] = value
    else:
        spec[path] = value


REPAIR_SYSTEM = """You transliterate Roman Urdu into Urdu script.

You are not translating and you are not rewriting. Every line you are given is
already Urdu — it is simply typed in Latin letters. Return the same sentence,
same words, same order, same meaning, written in Urdu script.

Keep any <em></em> tags exactly where they are. Keep hashtags as they are.
Output ONLY valid JSON."""


def repair(spec: dict, ask) -> dict:
    """Transliterate any Roman-Urdu lines in place. Raises if it cannot.

    `ask` is a function taking (system, user) and returning the model's text,
    passed in rather than imported so this module does not depend on which
    writer called it — and so it can be tested without an API key.
    """
    bad = offending(spec)
    if not bad:
        return spec

    print(f"  {len(bad)} line(s) came back in Roman Urdu — transliterating: "
          + ", ".join(p for p, _ in bad))
    payload = [{"id": p, "text": t} for p, t in bad]
    raw = ask(REPAIR_SYSTEM,
              "Rewrite each of these lines in Urdu script.\n\n"
              + json.dumps(payload, ensure_ascii=False, indent=2)
              + '\n\nRespond with ONLY: {"lines":[{"id":"...","text":"..."}]}')
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    fixed = {r["id"]: r["text"] for r in json.loads(raw).get("lines", [])}

    for path, original in bad:
        value = fixed.get(path)
        if not value or not is_urdu(value, 0.55):
            raise ValueError(
                f"{path} is still not in Urdu script after a transliteration "
                f"pass: {original[:60]!r}. Refusing to ship a video with mixed "
                f"scripts in its subtitles — that is the bug this check exists "
                f"for.")
        apply(spec, path, value)
    return spec
