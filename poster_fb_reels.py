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


def post_to_fb_reels(video_path: str, description: str) -> dict:
    if not configured():
        raise RuntimeError("FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not set")

    file_size = os.path.getsize(video_path)

    start = requests.post(f"{GRAPH_BASE}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "start", "access_token": FB_PAGE_ACCESS_TOKEN,
    }, timeout=30)
    if not start.ok:
        raise RuntimeError(f"FB Reels start failed ({start.status_code}): {start.text}")
    data = start.json()

    with open(video_path, "rb") as f:
        up = requests.post(data["upload_url"], headers={
            "Authorization": f"OAuth {FB_PAGE_ACCESS_TOKEN}",
            "offset": "0", "file_size": str(file_size),
        }, data=f.read(), timeout=300)
    if not up.ok:
        raise RuntimeError(f"FB Reels upload failed ({up.status_code}): {up.text}")

    fin = requests.post(f"{GRAPH_BASE}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "finish", "video_id": data["video_id"],
        "video_state": "PUBLISHED", "description": description,
        "access_token": FB_PAGE_ACCESS_TOKEN,
    }, timeout=60)
    if not fin.ok:
        raise RuntimeError(f"FB Reels finish failed ({fin.status_code}): {fin.text}")
    return fin.json()
