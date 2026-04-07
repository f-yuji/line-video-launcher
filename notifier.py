import requests

import config
from utils import setup_logger

logger = setup_logger("notifier")

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _push(user_id: str, text: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    res = requests.post(_PUSH_URL, json=payload, headers=headers, timeout=10)
    if res.status_code != 200:
        logger.error(f"[notifier] push failed: {res.status_code} {res.text}")
    else:
        logger.info(f"[notifier] pushed to {user_id}")


# ──────────────────────────────────────────────
# 生成完了
# ──────────────────────────────────────────────

def notify_generation_complete(user_id: str, post_id: str) -> None:
    text = (
        f"動画生成が完了しました！\n"
        f"投稿ID: {post_id}\n"
        f"ステータス: ready\n\n"
        f"「承認: {post_id}」で承認後、「投稿」で投稿できます。"
    )
    _push(user_id, text)


# ──────────────────────────────────────────────
# 投稿完了
# ──────────────────────────────────────────────

def notify_post_complete(user_id: str, post_id: str, succeeded_platforms: list[str]) -> None:
    platforms_str = "、".join(succeeded_platforms) if succeeded_platforms else "なし"
    text = (
        f"投稿が完了しました！\n"
        f"投稿ID: {post_id}\n"
        f"成功した媒体: {platforms_str}"
    )
    _push(user_id, text)


# ──────────────────────────────────────────────
# エラー通知
# ──────────────────────────────────────────────

def notify_error(user_id: str, post_id: str, step: str, reason: str) -> None:
    text = (
        f"エラーが発生しました。\n"
        f"投稿ID: {post_id}\n"
        f"失敗工程: {step}\n"
        f"理由: {reason}"
    )
    _push(user_id, text)


# ──────────────────────────────────────────────
# 将来 Flex Message 化用プレースホルダ
# ──────────────────────────────────────────────

def _build_flex_generation_complete(post_id: str) -> dict:
    """将来 Flex Message 化する際の受け皿（現在は未使用）"""
    return {
        "type": "flex",
        "altText": f"動画生成完了: {post_id}",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": f"生成完了: {post_id}", "weight": "bold"}
                ],
            },
        },
    }
