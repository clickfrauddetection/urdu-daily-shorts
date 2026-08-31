# urdu-daily-shorts

One Urdu vertical short a day — Facebook Reels and YouTube Shorts — built from
an HTML text layer composited over stock footage. No image model, no video
model. The only per-video cost is one Claude call for the script and the TTS.

Sibling repos: `social-media-posts-agent` (English, LinkedIn, square diagrams),
`tiktok-reels-agent` (Urdu, per-scene generated images). This one deliberately
takes a different rendering path from both — see below.

---

## Why the renderer is not `record_video`

Both sibling repos capture scenes with Playwright's `record_video`, which
writes a variable-frame-rate webm against the wall clock. The file always comes
back a little short, by an amount that depends on how fast the machine is.
Every `tpad=stop_mode=clone`, every measured `lead` offset, every "the closing
screen is three seconds adrift of the words describing it" fix in those repos is
a patch on that one fact — and the patches stop holding on a slow CI runner.

`renderer.py` never lets the browser's clock run. Animations are authored
paused, and each frame is made by seeking every animation to an exact time and
screenshotting:

```js
for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms; }
```

A 7.00s scene is 210 frames at 30fps on any machine. The narration offsets
`main.plan()` computes are therefore true by construction, and no padding is
ever needed.

Two more things fall out of it:

- Frames are captured **with alpha** (`omit_background`) and piped straight
  into ffmpeg as a lossless `qtrle` .mov. The background footage is composited
  underneath **in ffmpeg**, never in the browser — a `<video>` element decoded
  by Chromium cannot be seeked frame-accurately, which would put the drift
  straight back.
- Everything renders at 2x (`SCALE`) and ffmpeg downscales with lanczos. Urdu
  is thin, high-contrast type; at 1x the strokes alias and H.264 turns the
  shimmer into blocking.

## Layout

```
content.py    topic queue -> Claude -> an 8-scene script (fixed roles)
guard.py      refuses medical claims BEFORE anything is generated
voice_urdu.py Gemini TTS, Edge TTS fallback, word timings for the karaoke line
stock_bg.py   one Pixabay clip for the whole video, from a fixed theme list
templates/    the scene's HTML: RTL, two Urdu faces, scrim, safe zones
icons.py      inline SVG only — an unknown icon name raises, never falls back
renderer.py   frame-accurate alpha capture
assembler.py  composite, join, mux voice, duck a music bed
main.py       one clock for the whole video, then the two posters
```

## Setup

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
python fetch_fonts.py     # then commit ./fonts — CI needs them too
```

`ffmpeg` and `ffprobe` must be on PATH.

### Secrets

Copy the **same values** from the sibling repos — same Meta app, same Page,
same YouTube OAuth client. Nothing here needs a new app.

| Secret | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | writing the script |
| `GEMINI_API_KEY` | the good voice (falls back to free Edge TTS without it) |
| `OPENAI_API_KEY` | tier 3 of the voice ladder (optional) |
| `PIXABAY_API_KEY` | background footage |
| `REPLICATE_API_TOKEN` | generating a background when Pixabay has none (optional) |
| `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN` | Facebook Reels |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | Shorts |

Repo **variable** `NICHE` picks the channel (`sleep`, `focus`, …). It selects
the topic queue, the background themes and the hashtags — a second channel is a
second value here, not a second repo.

**Set the YouTube OAuth consent screen to "In production."** While it sits in
"Testing", Google expires the refresh token every 7 days. That has taken the
sibling repo down repeatedly.

## Running

```bash
python main.py                        # dry run: writes out/<niche>_<date>.mp4
python main.py --topic "..."          # skip the queue
python main.py --post                 # publish to both platforms
```

Every build writes `out/<name>.json` — the exact script the file was made from.
When a video performs, that is the only useful question.

## Four kinds of video, one channel

One Page, one YouTube channel, one set of secrets and one posted log — a second
Page would have meant a second audience to grow from zero for something that
can simply take turns. Everything that differs between the kinds is in the
`KINDS` table at the top of `main.py` and nowhere else, which is the only
reason one channel can carry four shapes without four of every function.

| | `habit` | `scripture` | `text` | `ibrat` |
|---|---|---|---|---|
| what | a wellness script | the day's ayah or hadith | a silent card | a story that ends on a verse |
| writes | `content.py`, 8 scenes | `content_islamic.py`, 5–7 | `content_text.py`, 1 | `content_ibrat.py`, 7 |
| guard | `guard.py` — medical claims | `guard_islamic.py` — integrity first | `guard.py` | `guard_ibrat.py` — integrity, then invented events |
| frame | `templates/scene.py` | `templates/scene_islamic.py` | `templates/scene_text.py` | both, per scene |
| voice | narrator | qari + recorded translation | none | narrator, then the recorded translation |
| bed | music | ambience, silent under the recitation | music | music, silent under the verse |
| queue | `data/topics.json` | `data/islamic_queue.json` | `data/topics.json` | `data/ibrat_queue.json` |

**Which one runs is the CLOCK's decision, not an alternation.** The workflow
reads the cron that fired: 01:00 UTC is scripture, 13:00 UTC is the text card.
A channel that posts the same kind of thing at the same time every day is one a
viewer can form a habit around. `CONTENT_KIND` and `--kind` are for manual runs
and for pinning; `habit` and `ibrat` are buildable by name but are not on the
calendar, and putting one there is a cron line in `daily.yml`.

Every queue counts **posted videos, not dates**, so a failed morning does not
flip anything, and a rehearsal that published nowhere does not burn an entry.

```bash
python build_queue.py                     # fill / top up the scripture queue
python main.py                            # whatever today's turn is
python main.py --kind scripture           # force one
python main.py --topic "quran 94:5"
python main.py --kind ibrat
python main.py --topic "taraazu par thora sa kam tolna"   # an ibrat situation
python main.py --topic "hadith 5907" --post
```

### `ibrat` — one moment, two choices

Naseem's ask, and the shape is the argument: the same ordinary afternoon told
twice.

    neki → natija_neki → gunah → natija_gunah → akhirat → the verse → follow

The two halves must be the **same situation**, not two situations. A good man
and then a different bad man is a fable about strangers; one person's afternoon
run twice is about the viewer. The frame carries which half you are in —
`content_ibrat.TONE` colours the good half green and the wrong half gold, using
the same two accents the habit template has meant "what to do" and "the
problem" with since the first video.

Two rules specific to this kind, both enforced rather than requested:

- **The model does not choose the verse.** `data/ibrat_queue.json` pairs each
  situation with the verse it closes on, by hand. A model asked to find a verse
  that fits a story it has just written will always find one that sounds like
  it fits, and that is the whole risk of the format, not a quality problem. So
  `--topic` **resolves against that queue** rather than replacing it: a topic
  that is not in the file is an instruction to add it there with its verse.
- **The story is an example and never an event.** `guard_ibrat.py` refuses the
  language of "a true incident", and refuses a prophet, a companion or an
  honorific in any model-written scene — a narration written by a model is an
  invented hadith with the isnad filed off. The caption says so too, in Urdu,
  above the sourcing line.

Everything `guard_islamic.py` already refuses still applies, including handing
out a verdict on where somebody ends up: the akhirat scene may say a person
will be *asked*, and may not say the answer.

### The sacred text is never written by a model

`islamic_sources.py` fetches it — `api.alquran.cloud` for the Arabic, an Urdu
translation and the per-ayah recitation mp3; `hadeethenc.com` for a hadith with
its takhreej, its grade and its published explanation. Those scenes are marked
`verbatim`, Claude is only ever asked for the hook, two explanation scenes, one
action and the follow, and `guard_islamic.check_integrity()` compares every
verbatim field against the source dict before a frame is rendered. A drift of
one word fails the build.

Three things follow from that and are worth knowing before changing anything:

* A hadith whose grade is not in `islamic_sources.SOUND_GRADES` is refused
  outright, not published with the grade line left blank. `build_queue.py`
  draws only from HadeethEnc category 5 (فضائل و آداب) — not fiqh, not the
  sect categories.
* The ayah scene is **recited**, not narrated. The audio is the qari's own, and
  nothing plays under it: `add_music(silence=…)` fades the bed out for that
  window rather than ducking it. If the recitation cannot be downloaded the
  frame holds in silence instead of a synthetic voice reading Arabic.
* The written scenes are searched for the language of quotation
  ("اللہ تعالیٰ فرماتے ہیں…"), rulings, sects, takfir and reward promises. A
  quotation the model introduces is a quotation the model invented.

The Uthmani text is set in **AmiriQuran** — `fetch_fonts.py` gets it, and
`probe_fonts()` requires it on every run, not only on a scripture morning: the
point is to fail before a build rather than on the day the alternation lands
there.

## Music

`data/music/` carries only what `assembler.MUSIC_ATTRIBUTION` has a licence
line for. `assembler.MUSIC_ATTRIBUTION` must carry a
Anything without an entry is skipped with a warning and the video ships
without a bed. This posts publicly under the Page's name, and the sibling repo
already carries four tracks that arrived in a merge with no attribution and no
licence checked.

`MUSIC_POLICY` (from the profile, overridable; `NO_MUSIC=1` forces `none`):

* `bed` — a scored music bed. The wellness channel.
* `ambient` — room tone, generated by `make_ambience.py` out of ffmpeg's own
  noise generator. No pitch, no beat, no melody, and its provenance is that
  file. This is what the scripture channel uses: instrumental music under
  recitation is not something an Urdu Islamic channel can do, and silence
  alone reads as a broken upload.
* `none` — nothing at all.

The three `timelens_bed_*.mp3` files inherited from Time Lens are **not** the
default for anything until someone confirms what they actually are.

## The guard

`guard.py` runs before a frame is rendered and is fatal by default. It refuses:
cure and treatment claims, any named condition or diagnosis, any medicine,
supplement, dose or quantity, "you don't need a doctor", and guarantees. Every
pattern is matched against Urdu script, Roman Urdu and English, because the
writer produces all three.

The point is not view count. A run of unread auto-generated advice needs one
clip claiming a cure to take a strike that costs the Page. Losing a day's post
is cheap by comparison.

Both disclaimers ride on every caption and description.

## Script, not language — why subtitles came out mixed

Videos shipped with Urdu subtitles on some scenes and Roman Urdu on others.
The renderer was not the cause: `templates/scene.py` already detects the script
per line and lays Latin text out left-to-right, so a wrong-script line degrades
to off-brand instead of to visually reversed nonsense. The cause was upstream —
`data/topics.json` is written in Roman Urdu because that is what is comfortable
to type, and a model asked a question in Latin letters now and then answers in
them. Nothing between the model and the frame ever checked.

`urdu.py` is that check, and it runs in both writers before anything is
narrated or rendered. A Latin line is transliterated back into Urdu script in
one small model call naming only the lines that failed, so the day's video is
not lost over it; a line still Latin after that is a hard failure. Scenes
marked `verbatim` are skipped — the Arabic is Arabic, and the translation is
the translator's.

## Topics and pillars

`data/topics.json`, keyed by niche. A niche is either a flat list, or an object
of **pillar → topics** — and the object form rotates.

The default niche `daily` has seven pillars: `neend`, `paisa`, `waqt`, `phone`,
`ghar`, `aadat`, `rishtay`. Each day's pillar is chosen by how many videos the
channel has already posted, so day 1 is sleep, day 2 is money, day 8 is sleep
again. A broad channel that ran five sleep topics in a row would be read as a
sleep channel by viewers and by the algorithm; the rotation is what keeps it
broad in practice rather than only in the topic file.

The pillar also picks the **background** — `stock_bg.THEMES` and
`replicate_bg.PILLAR_PROMPT` are both keyed by it, so a money topic opens on a
city skyline and not on a night sky. Adding a pillar means adding an entry to
all three.

Topics are filled by hand, never by the model: a model asked daily to "think of
a good topic" converges within about two weeks and starts rewording the same
four ideas. An exhausted pillar hands the day to the next one; every pillar
exhausted is a hard error rather than a quiet decline in quality.

## Backgrounds

Three tiers, in order:

1. **Pixabay** — free stock footage. One clip for the whole video. Every theme
   for the pillar is tried, shuffled, three attempts each with a rising
   backoff, then generic terms. A rejected key short-circuits the chain.
2. **Replicate** (`replicate_bg.py`) — only when Pixabay found nothing. Default
   `REPLICATE_BG_MODE=still`: one FLUX image (~$0.003), looped, animated by the
   compositor's existing drift. `motion` adds an LTX-Video clip (~$0.057) —
   worth knowing that tiktok-reels-agent turned that off because the clips came
   back uneven and one visibly spoiled a published video.
3. **A flat gradient.** Never an error. It is printed loudly, because a channel
   quietly running on gradients for a week is the failure worth worrying about.
