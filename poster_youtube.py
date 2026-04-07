"""
YouTube Shorts への動画投稿モジュール。
google-api-python-client + OAuth2 リフレッシュトークン方式を使用。
"""
import config
from utils import setup_logger

logger = setup_logger("poster_youtube")

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_youtube_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not all([
        config.YOUTUBE_CLIENT_ID,
        config.YOUTUBE_CLIENT_SECRET,
        config.YOUTUBE_REFRESH_TOKEN,
    ]):
        raise EnvironmentError("Missing required YouTube environment variables")
    creds = Credentials(
        token=None,
        refresh_token=config.YOUTUBE_REFRESH_TOKEN,
        token_uri=_TOKEN_URI,
        client_id=config.YOUTUBE_CLIENT_ID,
        client_secret=config.YOUTUBE_CLIENT_SECRET,
        scopes=_SCOPES,
    )
    # 期限切れなら自動リフレッシュ
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def post_to_youtube(
    post_id: str,
    video_path: str,
    title: str,
    description: str,
) -> dict:
    """
    動画を YouTube Shorts としてアップロードする。
    成功時は {"video_id": str, "url": str} を返す。
    """
    logger.info(f"[post_to_youtube] post_id={post_id} uploading")
    youtube = _get_youtube_service()
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],          # タイトル上限
            "description": description,
            "tags": ["Shorts"],
            "categoryId": "22",            # People & Blogs
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=256 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"[post_to_youtube] upload {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    logger.info(f"[post_to_youtube] posted video_id={video_id}")

    return {
        "video_id": video_id,
        "url": url,
    }


def build_youtube_title(script_first_line: str) -> str:
    """台本の1行目からタイトルを生成する（簡易版）"""
    title = script_first_line.strip()
    if len(title) > 90:
        title = title[:90] + "…"
    return title + " #Shorts"
