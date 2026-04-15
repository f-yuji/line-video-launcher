import argparse
import uuid

import caption_generator_v2 as caption_generator
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
    args = parser.parse_args()

    topic = (args.topic or "").strip()
    if not topic:
        topic = input("topic> ").strip()
    if not topic:
        raise SystemExit("topic is empty")

    ensure_dirs()
    post_id = str(uuid.uuid4())

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
    print(f"audio: {audio_path}")
    print(f"subtitle: {subtitle_path}")
    print(f"hook image: {hook_image_path}")
    print(f"cta image: {cta_image_path}")
    print(f"video: {video_path}")

    if args.captions:
        print()
        print("=== BODY ===")
        print(captions.body_text)
        print()
        print("=== HASHTAGS ===")
        print(captions.hashtags)


if __name__ == "__main__":
    main()
