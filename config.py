import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


def _optional(key: str) -> str | None:
    return os.environ.get(key)


# LINE
LINE_CHANNEL_ACCESS_TOKEN = _require("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = _require("LINE_CHANNEL_SECRET")

# Supabase
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_KEY = _require("SUPABASE_KEY")

# OpenAI
OPENAI_API_KEY = _optional("OPENAI_API_KEY")

# Gemini
GEMINI_API_KEY = _optional("GEMINI_API_KEY")
GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-2.5-flash-lite")

# ElevenLabs
ELEVENLABS_API_KEY = _optional("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = _optional("ELEVENLABS_VOICE_ID")
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_LANGUAGE_CODE = os.environ.get("ELEVENLABS_LANGUAGE_CODE", "ja")
ELEVENLABS_STABILITY = float(os.environ.get("ELEVENLABS_STABILITY", "0.5"))
ELEVENLABS_SIMILARITY_BOOST = float(os.environ.get("ELEVENLABS_SIMILARITY_BOOST", "0.75"))
ELEVENLABS_STYLE = float(os.environ.get("ELEVENLABS_STYLE", "0.0"))
ELEVENLABS_USE_SPEAKER_BOOST = os.environ.get("ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() == "true"

# X (Twitter)
X_API_KEY = _optional("X_API_KEY")
X_API_SECRET = _optional("X_API_SECRET")
X_ACCESS_TOKEN = _optional("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = _optional("X_ACCESS_TOKEN_SECRET")

# YouTube
YOUTUBE_CLIENT_ID = _optional("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = _optional("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = _optional("YOUTUBE_REFRESH_TOKEN")

# Directory paths
RAW_DIR = os.environ.get("RAW_DIR", "raw")
AUDIO_DIR = os.environ.get("AUDIO_DIR", "audio")
SUBTITLE_DIR = os.environ.get("SUBTITLE_DIR", "subtitles")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
LOG_DIR = os.environ.get("LOG_DIR", "logs")
VOICE_LEAD_IN_SECONDS = float(os.environ.get("VOICE_LEAD_IN_SECONDS", "1.0"))
