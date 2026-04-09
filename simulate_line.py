import argparse

import caption_generator_v2 as caption_generator
import script_generator_v13 as script_generator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local simulator for script and caption generation."
    )
    parser.add_argument(
        "--captions",
        action="store_true",
        help="also generate SNS captions",
    )
    args = parser.parse_args()

    print("LINE simulator")
    print("Type a topic and press Enter.")
    print("Commands: /quit, /exit, /captions on, /captions off")
    print()

    captions_enabled = args.captions

    while True:
        try:
            raw = input("topic> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        if not raw:
            continue
        if raw in {"/quit", "/exit"}:
            print("bye")
            return
        if raw == "/captions on":
            captions_enabled = True
            print("captions: on")
            continue
        if raw == "/captions off":
            captions_enabled = False
            print("captions: off")
            continue

        try:
            result = script_generator.generate_script(raw)
        except Exception as exc:
            print(f"[script error] {exc}")
            print()
            continue

        print()
        print("=== DISPLAY ===")
        print(result.display_text)
        print()
        print("=== SPEECH ===")
        print(result.speech_text)

        if captions_enabled:
            try:
                captions = caption_generator.generate_captions(result.speech_text)
            except Exception as exc:
                print()
                print(f"[caption error] {exc}")
                print()
                continue

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
            print("=== HASHTAGS ===")
            print(captions.hashtags)

        print()


if __name__ == "__main__":
    main()
