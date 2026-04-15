"""
Supabase Storage へのファイルアップロード。
動画ファイルをアップして公開URLを返す。
"""
import os

import config
from db import get_client
from utils import setup_logger

logger = setup_logger("storage")

_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "videos")


def upload_video(post_id: str, video_path: str) -> str:
    """
    動画ファイルを Supabase Storage にアップロードして公開URLを返す。
    同名ファイルが存在する場合は上書きする。
    """
    filename = os.path.basename(video_path)
    storage_path = f"{post_id}/{filename}"

    logger.info(f"[storage] uploading {filename} to bucket={_BUCKET}")

    with open(video_path, "rb") as f:
        get_client().storage.from_(_BUCKET).upload(
            path=storage_path,
            file=f,
            file_options={
                "content-type": "video/mp4",
                "upsert": "true",
            },
        )

    public_url = get_client().storage.from_(_BUCKET).get_public_url(storage_path)
    logger.info(f"[storage] uploaded: {public_url}")
    return public_url
