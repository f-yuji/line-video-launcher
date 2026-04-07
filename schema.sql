-- posts テーブル作成
CREATE TABLE IF NOT EXISTS posts (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_user_id             TEXT        NOT NULL,
    raw_text                 TEXT        NOT NULL,
    video_script             TEXT,
    speech_text              TEXT,
    body_text                TEXT,
    audio_path               TEXT,
    video_path               TEXT,
    subtitle_path            TEXT,
    x_text                   TEXT,
    youtube_text             TEXT,
    tiktok_text              TEXT,
    instagram_text           TEXT,
    hashtags                 TEXT,

    -- ステータス: draft / generating / ready / approved / posting / posted / error
    status                   TEXT        NOT NULL DEFAULT 'draft',
    error_message            TEXT,

    -- タイムスタンプ
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at              TIMESTAMPTZ,
    posted_at                TIMESTAMPTZ,
    generation_started_at    TIMESTAMPTZ,
    generation_completed_at  TIMESTAMPTZ,
    posting_started_at       TIMESTAMPTZ,

    -- 各媒体のステータス（"posted:{id}" / "error:..." / "manual_pending"）
    platform_status_x        TEXT,
    platform_status_youtube  TEXT,
    platform_status_tiktok   TEXT,
    platform_status_instagram TEXT
);

-- updated_at 自動更新トリガ
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_posts_updated_at
BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- インデックス
CREATE INDEX IF NOT EXISTS idx_posts_line_user_id ON posts (line_user_id);
CREATE INDEX IF NOT EXISTS idx_posts_status       ON posts (status);
CREATE INDEX IF NOT EXISTS idx_posts_created_at   ON posts (created_at DESC);

-- status の取りうる値をチェック制約で保護（将来の細分化に備えリスト管理）
ALTER TABLE posts
    ADD CONSTRAINT chk_posts_status
    CHECK (status IN (
        'draft', 'generating', 'ready',
        'approved', 'posting', 'posted', 'error'
    ));
