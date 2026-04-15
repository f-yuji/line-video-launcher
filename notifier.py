import requests

import config
from utils import setup_logger

logger = setup_logger("notifier")

_PUSH_URL = "https://api.line.me/v2/bot/message/push"

def _action_buttons_flex(post_id: str) -> dict:
    """投稿操作ボタンを Flex Message バブルで返す（チャットに残る）"""
    def _btn(label: str, text: str, color: str) -> dict:
        return {
            "type": "button",
            "style": "primary",
            "color": color,
            "margin": "sm",
            "action": {"type": "message", "label": label, "text": text},
        }

    return {
        "type": "flex",
        "altText": f"操作ボタン: {post_id}",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "paddingAll": "lg",
                "contents": [
                    {
                        "type": "text",
                        "text": post_id,
                        "size": "xs",
                        "color": "#aaaaaa",
                        "margin": "none",
                    },
                    _btn("✅ 投稿する",    f"投稿: {post_id}",    "#27ACB2"),
                    _btn("🔄 再生成",      f"再生成: {post_id}",  "#555555"),
                    _btn("#️⃣ タグ再生成", f"タグ再生成: {post_id}", "#888888"),
                ],
            },
        },
    }


def _headers() -> dict:
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }


def _push(user_id: str, text: str) -> None:
    """テキスト1通を送信する"""
    _push_messages(user_id, [{"type": "text", "text": text}])


def _push_messages(user_id: str, messages: list[dict]) -> None:
    """最大5通を一括送信する"""
    payload = {"to": user_id, "messages": messages[:5]}
    res = requests.post(_PUSH_URL, json=payload, headers=_headers(), timeout=15)
    if res.status_code != 200:
        logger.error(f"[notifier] push failed: {res.status_code} {res.text}")
    else:
        logger.info(f"[notifier] pushed {len(messages)} msg(s) to {user_id}")


def _text_msg(text: str) -> dict:
    return {"type": "text", "text": text}


def _video_msg(video_url: str, preview_url: str) -> dict:
    return {
        "type": "video",
        "originalContentUrl": video_url,
        "previewImageUrl": preview_url,
    }


# ──────────────────────────────────────────────
# 生成完了（シンプル版）
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
# 生成完了（投稿文・動画セット送信）
# ──────────────────────────────────────────────

def notify_generation_complete_with_content(
    user_id: str,
    post_id: str,
    body_text: str,
    hashtags: str,
    video_path: str,
) -> None:
    """
    生成完了後に本文・ハッシュタグ・動画をまとめてLINEへ送信する。
    """
    # 1通目: 本文 + ハッシュタグ（コピペ用）
    _push_messages(user_id, [
        _text_msg(f"{body_text}\n\n{hashtags}"),
    ])

    # 2通目: 動画
    _send_video(user_id, video_path, post_id)

    # 3通目: 操作ボタン
    _push_messages(user_id, [_action_buttons_flex(post_id)])

    logger.info(f"[notifier] sent content to {user_id} post_id={post_id}")


def _send_video(user_id: str, video_path: str, post_id: str) -> None:
    """
    Supabase Storage に動画をアップロードしてLINEに動画メッセージで送信。
    アップロード失敗時はエラー通知する。
    """
    try:
        import storage as _storage
        video_url = _storage.upload_video(post_id, video_path)
        _push_messages(user_id, [_video_msg(video_url, video_url)])
    except Exception as e:
        logger.error(f"[notifier] video upload failed: {e}")
        _push_messages(user_id, [
            _text_msg(f"動画のアップロードに失敗しました。\n{str(e)[:100]}")
        ])


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
