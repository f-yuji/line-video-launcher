FROM python:3.12-slim

# システムパッケージ: FFmpeg + 日本語フォント
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存パッケージ（コード変更時にキャッシュを活かす）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . .

# 生成ファイル用ディレクトリ
RUN mkdir -p raw audio subtitles output thumbnails logs

CMD gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --timeout 300 \
    --log-level info
