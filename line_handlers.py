"""
LINE コマンド分岐ハンドラ。
app.py から呼び出される。重い処理は worker に委譲する。
"""

import db
import worker
from utils import setup_logger

logger = setup_logger("line_handlers")

_PREFIX_REGISTER = "登録:"
_CMD_GENERATE = "生成"
_CMD_POST = "投稿"
_PREFIX_APPROVE = "承認:"   # 将来: 「承認: {id}」で ready → approved


def handle_message(user_id: str, text: str) -> str:
    """
    受信テキストを解析してコマンド処理を行い、即返信用テキストを返す。
    重い処理はここで実行しない。
    """
    stripped = text.strip()

    # ── 登録 ──
    if stripped.startswith(_PREFIX_REGISTER):
        return _handle_register(user_id, stripped)

    # ── 生成 ──
    if stripped == _CMD_GENERATE:
        return _handle_generate(user_id)

    # ── 投稿 ──
    if stripped == _CMD_POST:
        return _handle_post(user_id)

    # ── 承認（将来拡張用） ──
    if stripped.startswith(_PREFIX_APPROVE):
        return _handle_approve(user_id, stripped)

    # ── その他 ──
    return (
        "コマンド一覧:\n"
        "・登録: ネタ内容\n"
        "・生成\n"
        "・投稿\n"
        "・承認: {投稿ID}"
    )


# ──────────────────────────────────────────────
# 各コマンド処理
# ──────────────────────────────────────────────

def _handle_register(user_id: str, text: str) -> str:
    raw_text = text[len(_PREFIX_REGISTER):].strip()
    if not raw_text:
        return "ネタ内容を入力してください。例: 登録: 猫が水を怖がる理由"
    post = db.create_post(user_id, raw_text)
    logger.info(f"[handler] registered post_id={post['id']}")
    return f"ネタを登録しました！\n投稿ID: {post['id']}\nステータス: draft"


def _handle_generate(user_id: str) -> str:
    drafts = db.get_draft_posts(user_id)
    if not drafts:
        return "生成待ちのネタがありません。\n「登録: ネタ内容」でネタを登録してください。"

    ids = []
    for post in drafts:
        if not db.claim_post_for_generation(post["id"]):
            logger.info(f"[handler] skipped generation post_id={post['id']} (already claimed)")
            continue
        worker.enqueue_generation(post)
        ids.append(str(post["id"]))

    if not ids:
        return "生成対象はすでに処理開始済みでした。しばらく待ってから再確認してください。"

    ids_str = "\n".join(f"・{i}" for i in ids)
    logger.info(f"[handler] generation enqueued for {ids}")
    return (
        f"生成を開始しました！\n"
        f"対象 ({len(ids)}件):\n{ids_str}\n\n"
        f"完了したらLINEでお知らせします。"
    )


def _handle_post(user_id: str) -> str:
    approved = db.get_approved_posts(user_id)
    if not approved:
        return (
            "投稿可能なコンテンツがありません。\n"
            "「承認: {投稿ID}」でreadyのネタを承認してください。"
        )

    ids = []
    for post in approved:
        if not db.claim_post_for_posting(post["id"]):
            logger.info(f"[handler] skipped posting post_id={post['id']} (already claimed)")
            continue
        worker.enqueue_posting(post)
        ids.append(str(post["id"]))

    if not ids:
        return "投稿対象はすでに処理開始済みでした。しばらく待ってから再確認してください。"

    ids_str = "\n".join(f"・{i}" for i in ids)
    logger.info(f"[handler] posting enqueued for {ids}")
    return (
        f"投稿処理を開始しました！\n"
        f"対象 ({len(ids)}件):\n{ids_str}\n\n"
        f"完了したらLINEでお知らせします。"
    )


def _handle_approve(user_id: str, text: str) -> str:
    """「承認: {id}」で ready → approved に変更する"""
    post_id = text[len(_PREFIX_APPROVE):].strip()
    if not post_id:
        return "承認するIDを指定してください。例: 承認: abc123"

    post = db.get_post(post_id)
    if not post:
        return f"投稿ID {post_id} が見つかりません。"
    if post["line_user_id"] != user_id:
        return "他のユーザーの投稿は操作できません。"
    if post["status"] != "ready":
        return f"この投稿は承認できません。現在のステータス: {post['status']}"

    if not db.claim_post_for_approval(post_id):
        latest = db.get_post(post_id)
        latest_status = latest["status"] if latest else "unknown"
        return f"承認に失敗しました。現在のステータス: {latest_status}"

    logger.info(f"[handler] approved post_id={post_id}")
    return (
        f"承認しました！\n"
        f"投稿ID: {post_id}\n"
        f"「投稿」コマンドで投稿を開始できます。"
    )
