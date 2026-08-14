"""
poster_youtube_shorts.py
Uploads the finished file as a YouTube Short.

The title and description come from the script that was already written — no
second model call. The sibling repo asks Claude for an "SEO-optimised" title
after the fact, in English, for a video that is in Urdu; the result describes a
different video to the one it is attached to.

`defaultLanguage` and `defaultAudioLanguage` are both set to `ur`. Left unset,
YouTube guesses from the title, and an Urdu Short filed as English is served to
an English-speaking audience that scrolls straight past it — which reads as the
content failing when it is the metadata failing.
"""
import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.http

import guard
from config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, NICHE,
)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

DEAD_TOKEN_HELP = (
    "YOUTUBE_REFRESH_TOKEN is no longer valid (Google returned 'invalid_grant'). "
    "Google revokes refresh tokens after 7 days while the OAuth consent screen "
    "is still in 'Testing' publishing status — that is the usual cause and it "
    "has taken the sibling repo down repeatedly. Fix: set the consent screen to "
    "'In production' in Google Cloud Console, mint a new token with "
    "`python get_youtube_refresh_token.py`, and update the repo secret."
)

TAGS = {
    "sleep": ["نیند", "urdu", "sleep", "habits", "routine", "shorts",
              "urdu tips", "healthy habits", "sone ka tarika"],
    "default": ["urdu", "shorts", "habits", "routine", "urdu tips"],
}


def configured() -> bool:
    return all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN])


def _client():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def post_to_youtube_shorts(video_path: str, spec: dict) -> dict:
    if not configured():
        raise RuntimeError("YouTube secrets not configured")

    title = (spec.get("title") or spec["topic"])[:95]
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    description = (
        spec.get("caption", "") + "\n\n"
        + guard.DISCLAIMER_UR + "\n" + guard.DISCLAIMER_EN
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": TAGS.get(NICHE, TAGS["default"]),
            "categoryId": "22",
            "defaultLanguage": "ur",
            "defaultAudioLanguage": "ur",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }

    media = googleapiclient.http.MediaFileUpload(
        video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)

    try:
        request = _client().videos().insert(
            part="snippet,status", body=body, media_body=media)
        # The credentials are lazy — a dead refresh token surfaces here, on the
        # first chunk, not when the client is built.
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  YouTube upload: {int(status.progress() * 100)}%")
    except Exception as e:
        raise RuntimeError(DEAD_TOKEN_HELP if "invalid_grant" in str(e) else str(e)) from e

    url = f"https://www.youtube.com/shorts/{response['id']}"
    print(f"  YouTube Short: {url}")
    return {"id": response["id"], "url": url}
