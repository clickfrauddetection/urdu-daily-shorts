"""
get_youtube_refresh_token.py
Mints a fresh YOUTUBE_REFRESH_TOKEN for the upload workflow.

Run this locally (it opens a browser — it cannot run on the Actions
runner), sign in as the channel owner, then paste the printed value into
the repo's YOUTUBE_REFRESH_TOKEN secret.

    set YOUTUBE_CLIENT_ID=...          (PowerShell: $env:YOUTUBE_CLIENT_ID="...")
    set YOUTUBE_CLIENT_SECRET=...
    python get_youtube_refresh_token.py

BEFORE running, check the OAuth consent screen's publishing status in
Google Cloud Console (APIs & Services > OAuth consent screen). While it
says "Testing", Google expires every refresh token after 7 days and the
workflow will break again a week from now. Set it to "In production" —
no verification review is required for a token you issue to yourself.

The OAuth client must be of type "Desktop app"; a "Web application"
client rejects the loopback redirect this script uses.
"""
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

# The token is written here as well as printed, so it can be copied out
# of a file instead of scraped off a terminal that may have scrolled or
# be running unattended. Kept next to the repo (which is NOT cloud-synced)
# rather than under Desktop/Documents, which OneDrive would upload, and
# .gitignore'd so it can never be committed. Delete it once the value is
# in the GitHub secret.
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "youtube_refresh_token.txt")


def main() -> int:
    if not (CLIENT_ID and CLIENT_SECRET):
        print(
            "Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the "
            "environment first (use the same values as the repo secrets)."
        )
        return 1

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    # access_type=offline is what makes Google issue a refresh token at
    # all; prompt=consent forces a NEW one even when this account has
    # already granted the scope (otherwise the response comes back with
    # an access token only and no refresh token, which is the usual
    # reason people end up re-running this script confused).
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not creds.refresh_token:
        print(
            "No refresh token returned. Revoke this app at "
            "https://myaccount.google.com/permissions and run again."
        )
        return 1

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.refresh_token + "\n")

    print("\nSUCCESS — refresh token written to:")
    print(f"  {TOKEN_FILE}")
    print(
        "\nOpen that file, copy the single line inside, and paste it into "
        "the repo secret (Settings > Secrets and variables > Actions > "
        "YOUTUBE_REFRESH_TOKEN). Delete the file afterwards."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
