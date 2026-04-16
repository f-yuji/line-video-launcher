"""
X (Twitter) への動画投稿モジュール。
tweepy v4 + Twitter API v2 を使用。
"""
import config
from utils import setup_logger

logger = setup_logger("poster_x")
_X_HASHTAG_LIMIT = 3
_X_REPLY_LIMIT = 280


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


def post_reply_thread(root_tweet_id: str, body_text: str) -> list[str]:
    chunks = _split_reply_chunks(body_text, _X_REPLY_LIMIT)
    if not chunks:
        return []

    client = _get_client()
    reply_ids: list[str] = []
    parent_id = root_tweet_id

    for chunk in chunks:
        response = client.create_tweet(
            text=chunk,
            in_reply_to_tweet_id=parent_id,
        )
        parent_id = response.data["id"]
        reply_ids.append(parent_id)

    logger.info(f"[post_reply_thread] root={root_tweet_id} replies={len(reply_ids)}")
    return reply_ids


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


def _split_reply_chunks(text: str, limit: int) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= limit:
            current = paragraph
            continue

        chunks.extend(_split_long_text(paragraph, limit))

    if current:
        chunks.append(current)

    return chunks


def _split_long_text(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    remaining = text.strip()

    while len(remaining) > limit:
        split_at = max(
            remaining.rfind("。", 0, limit),
            remaining.rfind("！", 0, limit),
            remaining.rfind("？", 0, limit),
            remaining.rfind("\n", 0, limit),
            remaining.rfind(" ", 0, limit),
        )
        if split_at <= 0:
            split_at = limit
        else:
            split_at += 1

        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        parts.append(remaining)

    return parts
