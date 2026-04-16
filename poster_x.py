"""
X (Twitter) への動画投稿モジュール。
tweepy v4 + Twitter API v2 を使用。
"""
import config
from utils import setup_logger

logger = setup_logger("poster_x")
_X_HASHTAG_LIMIT = 3


def _get_client():
    import tweepy

    if not all([
        config.X_API_KEY,
        config.X_API_SECRET,
        config.X_ACCESS_TOKEN,
        config.X_ACCESS_TOKEN_SECRET,
    ]):
        raise EnvironmentError("Missing required X API environment variables")
    return tweepy.Client(
        consumer_key=config.X_API_KEY,
        consumer_secret=config.X_API_SECRET,
        access_token=config.X_ACCESS_TOKEN,
        access_token_secret=config.X_ACCESS_TOKEN_SECRET,
    )


def _get_api_v1():
    """メディアアップロードには v1.1 が必要"""
    import tweepy

    if not all([
        config.X_API_KEY,
        config.X_API_SECRET,
        config.X_ACCESS_TOKEN,
        config.X_ACCESS_TOKEN_SECRET,
    ]):
        raise EnvironmentError("Missing required X API environment variables")
    auth = tweepy.OAuth1UserHandler(
        config.X_API_KEY,
        config.X_API_SECRET,
        config.X_ACCESS_TOKEN,
        config.X_ACCESS_TOKEN_SECRET,
    )
    return tweepy.API(auth)


def post_to_x(post_id: str, video_path: str, text: str) -> dict:
    """
    動画ファイルと本文テキストを X に投稿する。
    成功時は {"tweet_id": str, "url": str} を返す。
    """
    logger.info(f"[post_to_x] post_id={post_id} uploading media")
    api_v1 = _get_api_v1()

    # 動画アップロード（chunked upload）
    media = api_v1.media_upload(
        filename=video_path,
        media_category="tweet_video",
        chunked=True,
    )
    media_id = media.media_id_string
    logger.info(f"[post_to_x] media uploaded: {media_id}")

    # ツイート作成
    client = _get_client()
    response = client.create_tweet(text=text, media_ids=[media_id])
    tweet_id = response.data["id"]
    url = f"https://x.com/i/web/status/{tweet_id}"
    logger.info(f"[post_to_x] posted tweet_id={tweet_id}")

    # 将来の再投稿に備えてIDを保持できる構造で返す
    return {
        "tweet_id": tweet_id,
        "url": url,
        "media_id": media_id,
    }


def build_x_post_text(text: str, hashtags: str = "") -> str:
    base = (text or "").strip()
    tags = _limit_hashtags(hashtags, _X_HASHTAG_LIMIT)
    if not tags:
        return base
    if not base:
        return tags
    return f"{base}\n\n{tags}"


def _limit_hashtags(hashtags: str, limit: int) -> str:
    parts = [part.strip() for part in (hashtags or "").split() if part.strip()]
    return " ".join(parts[:limit])
