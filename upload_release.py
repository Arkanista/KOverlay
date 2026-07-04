import requests
import json
import os

TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    print("GITHUB_TOKEN is not set")
    exit(1)
REPO = "Arkanista/koverlay"
TAG = "v0.1.7"
FILE_PATH = "koverlay-0.1.7-1-any.pkg.tar.zst"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# 1. Create Release
print(f"Creating release for {TAG}...")
response = requests.post(
    f"https://api.github.com/repos/{REPO}/releases",
    headers=headers,
    json={
        "tag_name": TAG,
        "name": f"Release {TAG}",
        "body": "Update includes Join/Leave History (+ / ✝) tracking and AI Text-to-Speech (TTS) Voice Announcements via edge-tts.",
        "draft": False,
        "prerelease": False
    }
)

if response.status_code == 201:
    release_data = response.json()
    upload_url = release_data["upload_url"].split("{")[0]
    print(f"Release created! Upload URL: {upload_url}")
elif response.status_code == 422: # Already exists
    print("Release already exists, fetching it...")
    resp2 = requests.get(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", headers=headers)
    release_data = resp2.json()
    upload_url = release_data["upload_url"].split("{")[0]
else:
    print(f"Failed to create release: {response.text}")
    exit(1)

# 2. Upload Asset
print(f"Uploading asset {FILE_PATH}...")
with open(FILE_PATH, "rb") as f:
    headers_upload = headers.copy()
    headers_upload["Content-Type"] = "application/zstd"
    res = requests.post(
        f"{upload_url}?name={os.path.basename(FILE_PATH)}",
        headers=headers_upload,
        data=f
    )
    if res.status_code == 201:
        print("Asset uploaded successfully!")
    else:
        print(f"Failed to upload asset: {res.text}")
