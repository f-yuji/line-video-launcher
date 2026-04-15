"""
投稿テストスクリプト。
既存の動画ファイルを指定してX・YouTubeに単体で投稿確認できる。

使い方:
  python test_post.py output/post_xxx_video.mp4
  python test_post.py output/post_xxx_video.mp4 --x-only
  python test_post.py output/post_xxx_video.mp4 --yt-only
"""
import argparse
import glob
import os

import poster_x
import poster_youtube
from utils import setup_logger

logger = setup_logger("test_post")

TEST_X_TEXT = "【テスト投稿】動作確認用です。すぐ削除します。 #詰み回避ラボ"
TEST_YT_TITLE = "【テスト】動作確認 #Shorts"
TEST_YT_DESCRIPTION = "動作確認用のテスト投稿です。すぐ削除します。"


def pick_latest_video() -> str:
    files = sorted(glob.glob("output/*.mp4"), key=os.path.getmtime, reverse=True)
    if not files:
        raise FileNotFoundError("output/ に動画ファイルが見つかりません")
    return files[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="投稿テスト")
    parser.add_argument("video", nargs="?", help="動画ファイルパス（省略時は output/ の最新ファイル）")
    parser.add_argument("--x-only", action="store_true", help="Xのみ投稿")
    parser.add_argument("--yt-only", action="store_true", help="YouTubeのみ投稿")
    args = parser.parse_args()

    video_path = args.video or pick_latest_video()
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    print(f"[test_post] 動画: {video_path}")
    post_id = "test"

    if not args.yt_only:
        print("[test_post] X に投稿中...")
        try:
            result = poster_x.post_to_x(post_id, video_path, TEST_X_TEXT)
            print(f"[test_post] X 投稿成功: {result['url']}")
        except Exception as e:
            print(f"[test_post] X 投稿失敗: {e}")

    if not args.x_only:
        print("[test_post] YouTube に投稿中...")
        try:
            result = poster_youtube.post_to_youtube(
                post_id, video_path, TEST_YT_TITLE, TEST_YT_DESCRIPTION
            )
            print(f"[test_post] YouTube 投稿成功: {result['url']}")
        except Exception as e:
            print(f"[test_post] YouTube 投稿失敗: {e}")


if __name__ == "__main__":
    main()
