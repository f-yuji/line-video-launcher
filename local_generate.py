import argparse
import uuid

import caption_generator_v3 as caption_generator
import config
import db
import script_generator_v13 as script_generator
import subtitle_generator_v4 as subtitle_generator
import thumbnail_generator_v2 as thumbnail_generator
import video_processor_v5 as video_processor
import voice_generator_v2 as voice_generator
from utils import ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one video locally without LINE."
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="topic or memo text to generate from",
    )
    parser.add_argument(
        "--captions",
        action="store_true",
        help="print generated body/caption text too",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="do not save generated result to Supabase",
    )
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
    post_record = None

    if db_enabled:
        print("[local] creating db post...")
        post_record = db.create_post(local_user_id, topic)
        post_id = post_record["id"]
        db.update_post_status(post_id, "generating")

    print(f"[local] post_id={post_id}")
    print("[local] generating script...")
    script_result = script_generator.generate_script(topic)
    display_script = script_result.speech_text
    speech_script = script_result.speech_text

    print("[local] generating captions...")
    captions = caption_generator.generate_captions(display_script)

    print("[local] generating voice...")
    audio_path = voice_generator.generate_voice(post_id, speech_script)

    print("[local] generating subtitles...")
    subtitle_path = subtitle_generator.generate_srt(post_id, display_script, audio_path)

    print("[local] generating hook image...")
    hook_image_path = thumbnail_generator.generate_hook_image(
        post_id,
        display_script.splitlines()[0] if display_script.splitlines() else "",
    )
    cta_image_path = thumbnail_generator.generate_cta_image(
        post_id,
        "詰み回避は本文で。",
    )

    print("[local] processing video...")
    video_path = video_processor.process_video(
        post_id,
        audio_path,
        subtitle_path,
        hook_text=display_script.splitlines()[0] if display_script.splitlines() else "",
        hook_image_path=hook_image_path,
        cta_image_path=cta_image_path,
    )

    print()
    print("=== DISPLAY ===")
    print(display_script)
    print()
    print("=== SPEECH ===")
    print(speech_script)
    print()
    print("=== BODY ===")
    print(captions.body_text)
    print()
    print("=== X ===")
    print(captions.x_text)
    print()
    print("=== YOUTUBE ===")
    print(captions.youtube_text)
    print()
    print("=== INSTAGRAM ===")
    print(captions.instagram_text)
    print()
    print("=== TIKTOK ===")
    print(captions.tiktok_text)
    print()
    print("=== HASHTAGS ===")
    print(captions.hashtags)
    print()
    print("=== GENERATED HASHTAGS ===")
    print(captions.generated_hashtags)
    print()
    print(f"audio: {audio_path}")
    print(f"subtitle: {subtitle_path}")
    print(f"hook image: {hook_image_path}")
    print(f"cta image: {cta_image_path}")
    print(f"video: {video_path}")

    if db_enabled:
        print("[local] saving generated content to db...")
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
        print(f"[local] saved to db: {post_id}")

if __name__ == "__main__":
    main()
