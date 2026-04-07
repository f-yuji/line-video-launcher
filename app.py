import hashlib
import hmac
import base64
import json

from flask import Flask, request, abort

import config
from utils import setup_logger, ensure_dirs
import line_handlers

logger = setup_logger("app")

app = Flask(__name__)


# ──────────────────────────────────────────────
# 署名検証
# ──────────────────────────────────────────────

def _verify_signature(body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(
            config.LINE_CHANNEL_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ──────────────────────────────────────────────
# LINE Reply
# ──────────────────────────────────────────────

import requests as _requests

def _reply(reply_token: str, text: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    res = _requests.post(
        "https://api.line.me/v2/bot/message/reply",
        json=payload,
        headers=headers,
        timeout=10,
    )
    if res.status_code != 200:
        logger.error(f"[reply] failed: {res.status_code} {res.text}")


# ──────────────────────────────────────────────
# Webhook
# ──────────────────────────────────────────────

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not _verify_signature(body, signature):
        logger.warning("[callback] invalid signature")
        abort(400)

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        abort(400)

    for event in payload.get("events", []):
        _handle_event(event)

    return "OK", 200


def _handle_event(event: dict) -> None:
    event_type = event.get("type")

    if event_type == "follow":
        _on_follow(event)
    elif event_type == "message":
        _on_message(event)
    else:
        logger.debug(f"[event] unhandled type={event_type}")


def _on_follow(event: dict) -> None:
    reply_token = event["replyToken"]
    user_id = event["source"]["userId"]
    logger.info(f"[follow] user={user_id}")
    _reply(
        reply_token,
        "フォローありがとうございます！\n\n"
        "使い方:\n"
        "・登録: ネタ内容 → ネタを登録\n"
        "・生成 → 動画生成開始\n"
        "・承認: {投稿ID} → 投稿を承認\n"
        "・投稿 → 承認済みを投稿",
    )


def _on_message(event: dict) -> None:
    message = event.get("message", {})
    if message.get("type") != "text":
        return

    reply_token = event["replyToken"]
    user_id = event["source"]["userId"]
    text = message.get("text", "")

    logger.info(f"[message] user={user_id} text={text[:50]!r}")

    # コマンド処理（重い処理は worker に委譲）
    reply_text = line_handlers.handle_message(user_id, text)

    # 即返信
    _reply(reply_token, reply_text)


# ──────────────────────────────────────────────
# 起動
# ──────────────────────────────────────────────

if __name__ == "__main__":
    ensure_dirs()
    logger.info("Starting LINE Video Launcher")
    app.run(host="0.0.0.0", port=5001, debug=False)
