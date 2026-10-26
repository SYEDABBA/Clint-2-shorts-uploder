import os
import re
import sys
import random
import mimetypes

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ==================================================
# CONFIGURATION
# ==================================================

YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
GD_REFRESH_TOKEN = os.environ.get("GD_REFRESH_TOKEN")

# Your NEW Google Drive folder
FOLDER_IDS = [
    "1buFdIWsi_MbcxMN8b9WK2qANHKGxlMWe"
]

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm",
    ".avi", ".m4v", ".mpeg", ".mpg"
}

VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/x-msvideo",
    "video/x-m4v",
    "video/mpeg"
}

CATEGORY_ID = "22"
PRIVACY_STATUS = os.environ.get(
    "YOUTUBE_PRIVACY_STATUS", "private"
).strip().lower()

# Keep uploads private until you verify the results.
if PRIVACY_STATUS not in {"private", "unlisted", "public"}:
    PRIVACY_STATUS = "private"

# Optional: set this GitHub secret to a custom title.
CUSTOM_TITLE = os.environ.get("VIDEO_TITLE", "").strip()

# Avoid selecting the same Drive video repeatedly.
# This stores the selected Drive IDs between GitHub Actions runs.
HISTORY_FILE = "uploaded_video_ids.txt"


# ==================================================
# SHAYARI SEO METADATA
# ==================================================

FIXED_TITLE = (
    "Dil Ko Chhoo Jane Wali Shayari 💔🥀 | "
    "Heart Touching Hindi Shayari #Shorts"
)

FIXED_DESCRIPTION = """
Kuch alfaaz seedha dil ko chhoo jaate hain... 💔🥀

Khamosh Qalam par suniye dil ki baat, mohabbat,
tanhai, adhuri kahaniyon aur zindagi ke jazbaat
se judi khoobsurat Hindi aur Urdu shayari.

Agar shayari aapke dil ko chhoo jaaye:
❤️ Video ko LIKE karein
💬 Apni feelings COMMENT mein batayein
🔔 Khamosh Qalam ko SUBSCRIBE karein

Aapki mohabbat aur support hamare liye bahut khaas hai. ❤️

#Shorts #Shayari #HindiShayari #SadShayari
#UrduShayari #HeartTouchingShayari #LoveShayari
#EmotionalShayari #SadStatus #HindiPoetry
#BrokenHeart #Mohabbat #KhamoshQalam

Note: Hashtags and descriptions do not guarantee
views or viral reach. Results depend on audience
interest, originality, retention and video quality.
"""

FIXED_TAGS = [
    "shayari",
    "hindi shayari",
    "urdu shayari",
    "sad shayari",
    "heart touching shayari",
    "love shayari",
    "emotional shayari",
    "sad status",
    "hindi poetry",
    "urdu poetry",
    "broken heart shayari",
    "mohabbat shayari",
    "dard bhari shayari",
    "romantic shayari",
    "two line shayari",
    "shayari shorts",
    "hindi shorts",
    "Khamosh Qalam"
]


# ==================================================
# ENVIRONMENT VALIDATION
# ==================================================

if not all([
    YT_REFRESH_TOKEN,
    YT_CLIENT_ID,
    YT_CLIENT_SECRET,
    GD_REFRESH_TOKEN
]):
    print("ERROR: Missing required GitHub Actions secrets.")
    print("Check YT_REFRESH_TOKEN, YT_CLIENT_ID,")
    print("YT_CLIENT_SECRET and GD_REFRESH_TOKEN.")
    sys.exit(1)


# ==================================================
# OAUTH CREDENTIALS
# ==================================================

def make_credentials(refresh_token, scopes):
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token.strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID.strip(),
        client_secret=YT_CLIENT_SECRET.strip(),
        scopes=scopes
    )

    credentials.refresh(Request())
    return credentials


def get_drive_service():
    credentials = make_credentials(
        GD_REFRESH_TOKEN,
        ["https://www.googleapis.com/auth/drive.readonly"]
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


def get_youtube_service():
    credentials = make_credentials(
        YT_REFRESH_TOKEN,
        ["https://www.googleapis.com/auth/youtube.upload"]
    )

    return build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


# ==================================================
# DRIVE VIDEO DISCOVERY
# ==================================================

def list_folder_items(drive, folder_id):
    items = []
    page_token = None

    while True:
        response = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=100,
            pageToken=page_token,
            orderBy="name",
            fields=(
                "nextPageToken,"
                "files(id,name,mimeType,size,webViewLink,"
                "shortcutDetails(targetId,targetMimeType))"
            ),
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return items


def find_videos(drive, folder_id, visited=None):
    if visited is None:
        visited = set()

    if folder_id in visited:
        return []

    visited.add(folder_id)
    found = []

    for item in list_folder_items(drive, folder_id):
        item_id = item["id"]
        name = item.get("name", "video")
        mime_type = item.get("mimeType", "")

        if mime_type == "application/vnd.google-apps.folder":
            found.extend(find_videos(drive, item_id, visited))
            continue

        # Resolve Drive shortcuts to their original targets.
        if mime_type == "application/vnd.google-apps.shortcut":
            details = item.get("shortcutDetails", {})
            target_id = details.get("targetId")
            target_mime = details.get("targetMimeType", "")

            if not target_id:
                print(f"Skipping shortcut without target: {name}")
                continue

            try:
                target = drive.files().get(
                    fileId=target_id,
                    fields="id,name,mimeType,size",
                    supportsAllDrives=True
                ).execute()

                name = target.get("name", name)
                mime_type = target.get("mimeType", target_mime)
                item_id = target_id

            except Exception as error:
                print(f"Cannot access shortcut {name}: {error}")
                continue

        extension = os.path.splitext(name)[1].lower()

        if (
            mime_type.startswith("video/")
            or extension in VIDEO_EXTENSIONS
        ):
            found.append({
                "id": item_id,
                "name": name,
                "mimeType": mime_type
            })

    # Deduplicate videos that appear more than once.
    unique = {}

    for video in found:
        unique[video["id"]] = video

    return list(unique.values())


# ==================================================
# PREVENT REPEATED UPLOADS
# ==================================================

def read_history():
    if not os.path.exists(HISTORY_FILE):
        return set()

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return {
                line.strip()
                for line in file
                if line.strip()
            }
    except OSError:
        return set()


def save_history(video_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as file:
        file.write(video_id + "\n")


# ==================================================
# DOWNLOAD VIDEO
# ==================================================

def download_video(drive, selected_video):
    video_id = selected_video["id"]
    video_name = selected_video["name"]

    extension = os.path.splitext(video_name)[1].lower()

    if extension not in VIDEO_EXTENSIONS:
        extension = mimetypes.guess_extension(
            selected_video.get("mimeType", "")
        ) or ".mp4"

    safe_extension = re.sub(r"[^a-zA-Z0-9.]", "", extension)
    video_path = f"temp_video{safe_extension}"

    print(f"Selected video: {video_name}")
    print("Downloading video from Google Drive...")

    request = drive.files().get_media(
        fileId=video_id,
        supportsAllDrives=True
    )

    with open(video_path, "wb") as output:
        downloader = MediaIoBaseDownload(
            output,
            request,
            chunksize=8 * 1024 * 1024
        )

        done = False

        while not done:
            status, done = downloader.next_chunk()

            if status:
                print(
                    f"Download progress: "
                    f"{int(status.progress() * 100)}%"
                )

    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        if os.path.exists(video_path):
            os.remove(video_path)

        raise RuntimeError(
            "Downloaded video is empty. Check Drive permissions."
        )

    print(
        f"Download complete: "
        f"{os.path.getsize(video_path)} bytes"
    )

    return video_path


# ==================================================
# YOUTUBE UPLOAD
# ==================================================

def upload_to_youtube(video_path, video_name):
    youtube = get_youtube_service()

    title = CUSTOM_TITLE or FIXED_TITLE

    body = {
        "snippet": {
            "title": title[:100],
            "description": FIXED_DESCRIPTION[:5000],
            "tags": FIXED_TAGS,
            "categoryId": CATEGORY_ID
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False
        }
    }

    mime_type = (
        mimetypes.guess_type(video_name)[0]
        or "video/mp4"
    )

    media = MediaFileUpload(
        video_path,
        mimetype=mime_type,
        chunksize=8 * 1024 * 1024,
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None

    while response is None:
        status, response = request.next_chunk()

        if status:
            print(f"YouTube upload: {int(status.progress() * 100)}%")

    video_id = response["id"]

    print("\nUPLOAD SUCCESSFUL!")
    print(f"Video ID: {video_id}")
    print(f"Video URL: https://www.youtube.com/watch?v={video_id}")
    print(f"Privacy status: {PRIVACY_STATUS}")

    return video_id


# ==================================================
# MAIN
# ==================================================

def main():
    print("=" * 50)
    print("KHAMOSH QALAM - YOUTUBE VIDEO UPLOADER")
    print("=" * 50)

    video_path = None
    selected_video = None

    try:
        drive = get_drive_service()
        all_videos = []

        for folder_id in FOLDER_IDS:
            print(f"\nSearching Drive folder: {folder_id}")

            videos = find_videos(drive, folder_id)
            print(f"Videos found: {len(videos)}")

            all_videos.extend(videos)

        unique = {
            video["id"]: video
            for video in all_videos
        }

        all_videos = list(unique.values())

        if not all_videos:
            print("\nERROR: No accessible videos found.")
            print("Check the folder ID, permissions, and shortcuts.")
            sys.exit(1)

        history = read_history()

        # Prefer videos that have not been uploaded before.
        remaining = [
            video for video in all_videos
            if video["id"] not in history
        ]

        if not remaining:
            print(
                "All discovered videos are in upload history. "
                "No video will be uploaded again."
            )
            sys.exit(0)

        selected_video = random.choice(remaining)

        video_path = download_video(drive, selected_video)

        video_id = upload_to_youtube(
            video_path,
            selected_video["name"]
        )

        # Record the source only after YouTube confirms success.
        save_history(selected_video["id"])

        print(f"Completed successfully: {video_id}")

    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")
        sys.exit(1)

    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                print("Temporary video deleted.")
            except OSError as error:
                print(f"Cleanup warning: {error}")


if __name__ == "__main__":
    main()
