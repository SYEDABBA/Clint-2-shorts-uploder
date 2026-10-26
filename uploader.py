import os
import random
import sys

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials


# ==================================================
# CONFIGURATION
# ==================================================

YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
GD_REFRESH_TOKEN = os.environ.get("GD_REFRESH_TOKEN")

# Google Drive folder ID
FOLDER_IDS = [
    "1dqcn78N_mRrx2LPM8klIXjj_tRR4OKhd"
]

FIXED_TITLE = (
    "Heart Touching Shayari 💔 | Sad Status 🥺✨ "
    "#shorts #shayari #viral"
)

FIXED_DESCRIPTION = """
Heart touching shayari 💔🥺

Dil ko chhoo jaane wale alfaaz, mohabbat ki yaadein,
aur zindagi ke unsune jazbaat. ❤️

Agar shayari pasand aaye to Like 👍 Share 💫
aur Channel ko Subscribe zaroor karein. 🙏❤️

#HeartTouchingShayari #SadShayari #HindiShayari
#UrduShayari #LoveShayari #SadStatus #Shayari
#Poetry #EmotionalShayari #BrokenHeart
#RomanticShayari #YouTubeShorts #Shorts
#ViralShorts #TrendingShorts

LIKE 😍
SHARE 💫
SUBSCRIBE 🙏❤️

Copyright Disclaimer:
Under Section 107 of the Copyright Act 1976, fair use
may apply to criticism, comment, news reporting,
teaching, scholarship, and research. Fair use depends
on the circumstances of each individual case.
"""

FIXED_TAGS = [
    "HeartTouchingShayari",
    "SadShayari",
    "RomanticShayari",
    "HindiShayari",
    "UrduShayari",
    "LoveShayari",
    "EmotionalShayari",
    "BrokenHeart",
    "SadStatus",
    "Shayari",
    "Poetry",
    "Shorts",
    "YouTubeShorts",
    "Trending",
    "ViralShorts"
]


# ==================================================
# VALIDATE ENVIRONMENT VARIABLES
# ==================================================

if not all([
    YT_REFRESH_TOKEN,
    YT_CLIENT_ID,
    YT_CLIENT_SECRET,
    GD_REFRESH_TOKEN
]):
    print("ERROR: Required environment secrets are missing.")
    sys.exit(1)


# ==================================================
# GOOGLE DRIVE AUTHENTICATION
# ==================================================

def get_drive_service():
    credentials = Credentials(
        token=None,
        refresh_token=GD_REFRESH_TOKEN.strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID.strip(),
        client_secret=YT_CLIENT_SECRET.strip()
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


# ==================================================
# YOUTUBE AUTHENTICATION
# ==================================================

def get_youtube_service():
    credentials = Credentials(
        token=None,
        refresh_token=YT_REFRESH_TOKEN.strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID.strip(),
        client_secret=YT_CLIENT_SECRET.strip()
    )

    return build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


# ==================================================
# DOWNLOAD RANDOM VIDEO FROM GOOGLE DRIVE
# ==================================================

def get_video_from_drive():
    print("Connecting to Google Drive...")

    drive_service = get_drive_service()
    selected_folder = random.choice(FOLDER_IDS)

    query = (
        f"'{selected_folder}' in parents "
        "and mimeType contains 'video/' "
        "and trashed = false"
    )

    videos = []
    page_token = None

    while True:
        results = drive_service.files().list(
            q=query,
            fields="nextPageToken,files(id,name,mimeType)",
            pageSize=100,
            pageToken=page_token
        ).execute()

        videos.extend(results.get("files", []))
        page_token = results.get("nextPageToken")

        if not page_token:
            break

    if not videos:
        print("ERROR: No videos found in the Drive folder.")
        return None, None

    selected_video = random.choice(videos)

    video_id = selected_video["id"]
    video_name = selected_video["name"]

    extension = os.path.splitext(video_name)[1] or ".mp4"
    video_path = f"temp_raw_video{extension}"

    print(f"Selected video: {video_name}")
    print("Downloading video...")

    request = drive_service.files().get_media(
        fileId=video_id
    )

    with open(video_path, "wb") as file:
        downloader = MediaIoBaseDownload(file, request)

        done = False

        while not done:
            status, done = downloader.next_chunk()

            if status:
                progress = int(status.progress() * 100)
                print(f"Download progress: {progress}%")

    print("Video downloaded successfully.")

    return video_path, video_name


# ==================================================
# UPLOAD VIDEO TO YOUTUBE
# ==================================================

def upload_to_youtube(video_path):
    print("Connecting to YouTube...")

    youtube = get_youtube_service()

    body = {
        "snippet": {
            "title": FIXED_TITLE[:100],
            "description": FIXED_DESCRIPTION,
            "tags": FIXED_TAGS,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        video_path,
        chunksize=8 * 1024 * 1024,
        resumable=True,
        mimetype="video/*"
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
            progress = int(status.progress() * 100)
            print(f"Upload progress: {progress}%")

    video_id = response.get("id")

    print("UPLOAD SUCCESSFUL!")
    print(f"Video ID: {video_id}")
    print(f"Video URL: https://www.youtube.com/watch?v={video_id}")
    print("Privacy: Private")

    return video_id


# ==================================================
# MAIN
# ==================================================

def main():
    print("=" * 45)
    print("SHAYARI VIDEO UPLOADER")
    print("=" * 45)

    video_path = None

    try:
        video_path, video_name = get_video_from_drive()

        if not video_path:
            return

        upload_to_youtube(video_path)

    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                print("Temporary video file cleaned up.")
            except OSError as error:
                print(f"Cleanup warning: {error}")


if __name__ == "__main__":
    main()
