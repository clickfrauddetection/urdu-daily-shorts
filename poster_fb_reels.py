"""
poster_fb_reels.py
Publishes a Reel to a Facebook Page — start / transfer / finish.

Lifted unchanged in shape from tiktok-reels-agent. Same Meta app, same Page,
same token: copy the secret VALUES across, no new app review needed.
"""
import os

import requests

from config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, GRAPH_API_VERSION

GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def configured() -> bool:
    return bool(FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN)


def post_to_fb_reels(video_path: str, description: str,
                     page_id: str = "", token: str = "") -> dict:
    """Publish a reel. Defaults to the channel's own page.

    page_id/token let the same video go to a SECOND page without a second
    poster — see config.FB_SYNDICATE. Passing one means passing both: a page
    id with the wrong page's token uploads to neither and the error Facebook
    returns for it names neither.
    """
    page_id = page_id or FB_PAGE_ID
    token = token or FB_PAGE_ACCESS_TOKEN
    if not (page_id and token):
        raise RuntimeError("FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not set")

    file_size = os.path.getsize(video_path)

    start = requests.post(f"{GRAPH_BASE}/{page_id}/video_reels", data={
        "upload_phase": "start", "access_token": token,
    }, timeout=30)
    if not start.ok:
        raise RuntimeError(f"FB Reels start failed ({start.status_code}): {start.text}")
    data = start.json()

    with open(video_path, "rb") as f:
        up = requests.post(data["upload_url"], headers={
            "Authorization": f"OAuth {token}",
            "offset": "0", "file_size": str(file_size),
        }, data=f.read(), timeout=300)
    if not up.ok:
        raise RuntimeError(f"FB Reels upload failed ({up.status_code}): {up.text}")

    fin = requests.post(f"{GRAPH_BASE}/{page_id}/video_reels", data={
        "upload_phase": "finish", "video_id": data["video_id"],
        "video_state": "PUBLISHED", "description": description,
        "access_token": token,
    }, timeout=60)
    if not fin.ok:
        raise RuntimeError(f"FB Reels finish failed ({fin.status_code}): {fin.text}")
    return fin.json()
