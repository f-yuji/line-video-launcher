"""
生成から投稿まで一気通貫のテストスクリプト。

使い方:
  python test_full.py "マイホームの書類管理"
  python test_full.py "マイホームの書類管理" --no-post   # 生成だけして投稿しない
  python test_full.py "マイホームの書類管理" --no-db     # DB保存しない
"""
import argparse
import uuid

import caption_generator_v3 as caption_generator
import config
import db
import poster_x
import poster_youtube
import script_generator_v13 as script_generator
import subtitle_generator_v4 as subtitle_generator
import thumbnail_generator_v2 as thumbnail_generator
import video_processor_v5 as video_processor
import voice_generator_v2 as voice_generator
from utils import ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(description="生成〜投稿 一気通貫テスト")
    parser.add_argument("topic", nargs="?", help="ネタテキスト")
    parser.add_argument("--no-post", action="store_true", help="投稿をスキップ")
    parser.add_argument("--no-db", action="store_true", help="DB保存をスキップ")
    args = parser.parse_args()

    topic = (args.topic or "").strip()
    if not topic:
        topic = input("topic> ").strip()
    if not topic:
        raise SystemExit("topic is empty")

    ensure_dirs()
    post_id = str(uuid.uuid4())
    db_enabled = not args.no_db
    local_user_id = getattr(config, "LOCAL_LINE_USER_ID", "local_cli")

    if db_enabled:
        print("[test] DB にpost作成...")
        post_record = db.create_post(local_user_id, topic)
        post_id = post_record["id"]
        db.update_post_status(post_id, "generating")

    print(f"[test] post_id={post_id}")

    # ── 生成フェーズ ──
    print("[test] 台本生成中...")
    script_result = script_generator.generate_script(topic)
    display_script = script_result.display_text
    speech_script = script_result.speech_text

    print("[test] 投稿文生成中...")
    captions = caption_generator.generate_captions(display_script)

    print("[test] 音声生成中...")
    audio_path = voice_generator.generate_voice(post_id, speech_script)

    print("[test] 字幕生成中...")
    subtitle_path = subtitle_generator.generate_srt(post_id, display_script, audio_path)

    print("[test] フック画像生成中...")
    hook_image_path = thumbnail_generator.generate_hook_image(
        post_id,
        display_script.splitlines()[0] if display_script.splitlines() else "",
    )
    cta_image_path = thumbnail_generator.generate_cta_image(post_id, "詰み回避は本文で。")

    print("[test] 動画生成中...")
    video_path = video_processor.process_video(
        post_id,
        audio_path,
        subtitle_path,
        hook_text=display_script.splitlines()[0] if display_script.splitlines() else "",
        hook_image_path=hook_image_path,
        cta_image_path=cta_image_path,
    )

    # ── 生成結果表示 ──
    print("\n=== DISPLAY ===")
    print(display_script)
    print("\n=== X ===")
    print(captions.x_text)
    print("\n=== YOUTUBE ===")
    print(captions.youtube_text)
    print("\n=== HASHTAGS ===")
    print(captions.hashtags)
    print(f"\nvideo: {video_path}")

    if db_enabled:
        print("\n[test] DB に保存中...")
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

    if args.no_post:
        print("\n[test] --no-post 指定のため投稿スキップ")
        return

    # ── 投稿フェーズ ──
    x_text_with_tags = f"{captions.x_text}\n\n{captions.hashtags}"

    print("\n[test] X に投稿中...")
    try:
        x_result = poster_x.post_to_x(post_id, video_path, x_text_with_tags)
        print(f"[test] X 投稿成功: {x_result['url']}")
        if db_enabled:
            db.update_platform_statuses(post_id, platform_status_x=f"posted:{x_result['tweet_id']}")
    except Exception as e:
        print(f"[test] X 投稿失敗: {e}")
        if db_enabled:
            db.update_platform_statuses(post_id, platform_status_x=f"error:{str(e)[:100]}")

    print("\n[test] YouTube に投稿中...")
    try:
        title = poster_youtube.build_youtube_title(display_script.splitlines()[0])
        yt_result = poster_youtube.post_to_youtube(
            post_id, video_path, title, captions.youtube_text
        )
        print(f"[test] YouTube 投稿成功: {yt_result['url']}")
        if db_enabled:
            db.update_platform_statuses(post_id, platform_status_youtube=f"posted:{yt_result['video_id']}")
    except Exception as e:
        print(f"[test] YouTube 投稿失敗: {e}")
        if db_enabled:
            db.update_platform_statuses(post_id, platform_status_youtube=f"error:{str(e)[:100]}")

    if db_enabled:
        db.update_posted_content(post_id)

    print("\n[test] 完了")


if __name__ == "__main__":
    main()
