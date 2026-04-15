"""
バックグラウンドワーカー。

現在は threading.Thread による簡易実装。
関数シグネチャを変えずに RQ / Celery への移行が可能。
"""
import threading
from typing import Optional

import config
import db
import notifier
import script_generator_v13 as script_generator
import caption_generator_v3 as caption_generator
import voice_generator_v2 as voice_generator
import subtitle_generator_v4 as subtitle_generator
import thumbnail_generator_v2 as thumbnail_generator
import video_processor_v5 as video_processor
import poster_x
import poster_youtube
from utils import setup_logger, ensure_dirs

logger = setup_logger("worker")


# ──────────────────────────────────────────────
# 生成ワーカー
# ──────────────────────────────────────────────

def _run_generation(post: dict) -> None:
    post_id = post["id"]
    user_id = post["line_user_id"]
    step = "init"
    try:
        ensure_dirs()

        # 台本生成
        step = "script"
        logger.info(f"[worker] [{post_id}] generating script")
        script_result = script_generator.generate_script(post["raw_text"])
        display_script = script_result.speech_text
        speech_script = script_result.speech_text

        # 投稿文生成
        step = "caption"
        logger.info(f"[worker] [{post_id}] generating captions")
        captions = caption_generator.generate_captions(display_script)

        # 音声生成（OpenAIが生成した音声用テキストを使用）
        step = "voice"
        logger.info(f"[worker] [{post_id}] generating voice")
        audio_path = voice_generator.generate_voice(post_id, speech_script)

        # 字幕生成
        step = "subtitle"
        logger.info(f"[worker] [{post_id}] generating subtitle")
        subtitle_path = subtitle_generator.generate_srt(post_id, display_script, audio_path)

        step = "thumbnail"
        logger.info(f"[worker] [{post_id}] generating hook images")
        hook_image_path = thumbnail_generator.generate_hook_image(
            post_id,
            script_result.hook_lines,
        )
        cta_image_path = thumbnail_generator.generate_cta_image(
            post_id,
            config.END_CTA_TEXT if hasattr(config, "END_CTA_TEXT") else "詰み回避は本文で。",
        )

        # 動画生成
        step = "video"
        logger.info(f"[worker] [{post_id}] processing video")
        video_path = video_processor.process_video(
            post_id,
            audio_path,
            subtitle_path,
            hook_text=display_script.splitlines()[0] if display_script.splitlines() else "",
            hook_image_path=hook_image_path,
            cta_image_path=cta_image_path,
        )

        # DB 更新
        step = "db_update"
        db.update_generated_content(
            post_id=post_id,
            video_script=display_script,
            speech_text=speech_script,
            body_text=captions.body_text,
            x_text=captions.x_text,
            youtube_text=captions.youtube_text,
            tiktok_text=captions.tiktok_text,
            instagram_text=captions.instagram_text,
            hashtags=captions.hashtags,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            video_path=video_path,
        )

        # LINE 通知（投稿文・動画セット送信）
        notifier.notify_generation_complete_with_content(
            user_id=user_id,
            post_id=post_id,
            body_text=captions.body_text,
            hashtags=captions.hashtags,
            video_path=video_path,
        )
        logger.info(f"[worker] [{post_id}] generation complete")


    except Exception as e:
        err_msg = f"[{step}] {type(e).__name__}: {str(e)[:300]}"
        logger.error(f"[worker] [{post_id}] FAILED {err_msg}", exc_info=True)
        db.update_post_status(post_id, "error", error_message=err_msg)
        notifier.notify_error(user_id, post_id, step=step, reason=str(e)[:200])


def enqueue_generation(post: dict) -> None:
    """生成ジョブをバックグラウンドで起動する"""
    t = threading.Thread(
        target=_run_generation,
        args=(post,),
        daemon=True,
        name=f"gen-{post['id']}",
    )
    t.start()
    logger.info(f"[worker] enqueued generation for post_id={post['id']}")


# ──────────────────────────────────────────────
# 投稿ワーカー
# ──────────────────────────────────────────────

def _run_posting(post: dict) -> None:
    post_id = post["id"]
    user_id = post["line_user_id"]
    succeeded: list[str] = []
    failed: list[str] = []
    try:
        # X 投稿
        logger.info(f"[worker] [{post_id}] posting to X")
        x_result = poster_x.post_to_x(
            post_id=post_id,
            video_path=post["video_path"],
            text=post["x_text"],
        )
        db.update_platform_statuses(
            post_id,
            platform_status_x=f"posted:{x_result['tweet_id']}",
        )
        succeeded.append("X")

    except Exception as e:
        err_x = f"[x] {type(e).__name__}: {str(e)[:200]}"
        logger.warning(f"[worker] [{post_id}] X failed: {err_x}")
        db.update_platform_statuses(
            post_id,
            platform_status_x=f"error:{str(e)[:100]}",
        )
        failed.append(err_x)

    try:
        # YouTube 投稿
        logger.info(f"[worker] [{post_id}] posting to YouTube")
        script_lines = post.get("video_script", "").splitlines()
        title = poster_youtube.build_youtube_title(
            script_lines[0] if script_lines else post.get("raw_text", "")[:90]
        )
        yt_result = poster_youtube.post_to_youtube(
            post_id=post_id,
            video_path=post["video_path"],
            title=title,
            description=post["youtube_text"],
        )
        db.update_platform_statuses(
            post_id,
            platform_status_youtube=f"posted:{yt_result['video_id']}",
        )
        succeeded.append("YouTube")

    except Exception as e:
        err_yt = f"[youtube] {type(e).__name__}: {str(e)[:200]}"
        logger.warning(f"[worker] [{post_id}] YouTube failed: {err_yt}")
        db.update_platform_statuses(
            post_id,
            platform_status_youtube=f"error:{str(e)[:100]}",
        )
        failed.append(err_yt)

    # TikTok / Instagram は手動投稿用テキストをDBに保存するのみ
    db.update_platform_statuses(
        post_id,
        platform_status_tiktok="manual_pending",
        platform_status_instagram="manual_pending",
    )

    if succeeded:
        error_summary = " / ".join(failed[:3]) if failed else None
        db.update_platform_statuses(post_id, error_message=error_summary)
        db.update_posted_content(post_id)
        notifier.notify_post_complete(user_id, post_id, succeeded)
        logger.info(
            f"[worker] [{post_id}] posting complete succeeded={succeeded} failed={failed}"
        )
        return

    retry_reason = "All auto-post targets failed"
    if failed:
        retry_reason += f": {' / '.join(failed[:3])}"
    db.update_platform_statuses(post_id, error_message=retry_reason[:500])
    db.update_post_status(post_id, "approved", error_message=retry_reason[:500])
    notifier.notify_error(user_id, post_id, step="posting", reason=retry_reason[:200])
    logger.warning(f"[worker] [{post_id}] posting failed on all targets")


def enqueue_posting(post: dict) -> None:
    """投稿ジョブをバックグラウンドで起動する"""
    t = threading.Thread(
        target=_run_posting,
        args=(post,),
        daemon=True,
        name=f"post-{post['id']}",
    )
    t.start()
    logger.info(f"[worker] enqueued posting for post_id={post['id']}")
