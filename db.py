from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client

import config
from utils import setup_logger

logger = setup_logger("db")

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


# ──────────────────────────────────────────────
# CREATE
# ──────────────────────────────────────────────

def create_post(line_user_id: str, raw_text: str) -> dict:
    data = {
        "line_user_id": line_user_id,
        "raw_text": raw_text,
        "status": "draft",
    }
    res = get_client().table("posts").insert(data).execute()
    record = res.data[0]
    logger.info(f"[create_post] id={record['id']} user={line_user_id}")
    return record


# ──────────────────────────────────────────────
# READ
# ──────────────────────────────────────────────

def get_draft_posts(line_user_id: str) -> list[dict]:
    res = (
        get_client()
        .table("posts")
        .select("*")
        .eq("line_user_id", line_user_id)
        .eq("status", "draft")
        .order("created_at")
        .execute()
    )
    return res.data


def get_approved_posts(line_user_id: str) -> list[dict]:
    res = (
        get_client()
        .table("posts")
        .select("*")
        .eq("line_user_id", line_user_id)
        .eq("status", "approved")
        .order("created_at")
        .execute()
    )
    return res.data


def get_ready_posts(line_user_id: str) -> list[dict]:
    res = (
        get_client()
        .table("posts")
        .select("*")
        .eq("line_user_id", line_user_id)
        .eq("status", "ready")
        .order("created_at")
        .execute()
    )
    return res.data


def get_post(post_id: str) -> Optional[dict]:
    res = (
        get_client()
        .table("posts")
        .select("*")
        .eq("id", post_id)
        .single()
        .execute()
    )
    return res.data


# ──────────────────────────────────────────────
# UPDATE – status
# ──────────────────────────────────────────────

def update_post_status(
    post_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    payload: dict = {"status": status}
    if error_message is not None:
        payload["error_message"] = error_message
    # ステータス別タイムスタンプ
    now = datetime.now(timezone.utc).isoformat()
    if status == "generating":
        payload["generation_started_at"] = now
    elif status == "ready":
        payload["generation_completed_at"] = now
    elif status == "approved":
        payload["approved_at"] = now
    elif status == "posting":
        payload["posting_started_at"] = now
    elif status == "posted":
        payload["posted_at"] = now

    get_client().table("posts").update(payload).eq("id", post_id).execute()
    logger.info(f"[update_post_status] id={post_id} -> {status}")


def update_platform_statuses(
    post_id: str,
    *,
    platform_status_x: Optional[str] = None,
    platform_status_youtube: Optional[str] = None,
    platform_status_tiktok: Optional[str] = None,
    platform_status_instagram: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    payload: dict = {}
    if platform_status_x is not None:
        payload["platform_status_x"] = platform_status_x
    if platform_status_youtube is not None:
        payload["platform_status_youtube"] = platform_status_youtube
    if platform_status_tiktok is not None:
        payload["platform_status_tiktok"] = platform_status_tiktok
    if platform_status_instagram is not None:
        payload["platform_status_instagram"] = platform_status_instagram
    if error_message is not None:
        payload["error_message"] = error_message
    if not payload:
        return

    get_client().table("posts").update(payload).eq("id", post_id).execute()
    logger.info(f"[update_platform_statuses] id={post_id}")


# ──────────────────────────────────────────────
# UPDATE – generated content
# ──────────────────────────────────────────────

def update_generated_content(
    post_id: str,
    video_script: str,
    speech_text: str,
    body_text: str,
    x_text: str,
    youtube_text: str,
    tiktok_text: str,
    instagram_text: str,
    hashtags: str,
    audio_path: str,
    subtitle_path: str,
    video_path: str,
) -> None:
    payload = {
        "video_script": video_script,
        "speech_text": speech_text,
        "body_text": body_text,
        "x_text": x_text,
        "youtube_text": youtube_text,
        "tiktok_text": tiktok_text,
        "instagram_text": instagram_text,
        "hashtags": hashtags,
        "audio_path": audio_path,
        "subtitle_path": subtitle_path,
        "video_path": video_path,
        "status": "ready",
        "generation_completed_at": datetime.now(timezone.utc).isoformat(),
    }
    get_client().table("posts").update(payload).eq("id", post_id).execute()
    logger.info(f"[update_generated_content] id={post_id}")


# ──────────────────────────────────────────────
# UPDATE – posted content
# ──────────────────────────────────────────────

def update_posted_content(
    post_id: str,
    platform_status_x: Optional[str] = None,
    platform_status_youtube: Optional[str] = None,
    platform_status_tiktok: Optional[str] = None,
    platform_status_instagram: Optional[str] = None,
) -> None:
    payload: dict = {
        "status": "posted",
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    if platform_status_x is not None:
        payload["platform_status_x"] = platform_status_x
    if platform_status_youtube is not None:
        payload["platform_status_youtube"] = platform_status_youtube
    if platform_status_tiktok is not None:
        payload["platform_status_tiktok"] = platform_status_tiktok
    if platform_status_instagram is not None:
        payload["platform_status_instagram"] = platform_status_instagram

    get_client().table("posts").update(payload).eq("id", post_id).execute()
    logger.info(f"[update_posted_content] id={post_id}")


# ──────────────────────────────────────────────
# APPROVE (ready → approved)
# ──────────────────────────────────────────────

def approve_post(post_id: str) -> None:
    update_post_status(post_id, "approved")
    logger.info(f"[approve_post] id={post_id}")


def claim_post_for_generation(post_id: str) -> bool:
    payload = {
        "status": "generating",
        "generation_started_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    }
    res = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("status", "draft")
        .execute()
    )
    claimed = bool(res.data)
    logger.info(f"[claim_post_for_generation] id={post_id} claimed={claimed}")
    return claimed


def claim_post_for_approval(post_id: str) -> bool:
    payload = {
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    res = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("status", "ready")
        .execute()
    )
    claimed = bool(res.data)
    logger.info(f"[claim_post_for_approval] id={post_id} claimed={claimed}")
    return claimed


def claim_post_for_posting(post_id: str) -> bool:
    payload = {
        "status": "posting",
        "posting_started_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    }
    res = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("status", "approved")
        .execute()
    )
    claimed = bool(res.data)
    logger.info(f"[claim_post_for_posting] id={post_id} claimed={claimed}")
    return claimed
