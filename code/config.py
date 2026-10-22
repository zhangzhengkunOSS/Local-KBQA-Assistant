import os
from pathlib import Path

# 因为文件在 code/ 下，所以项目根目录是上一级
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _path(env_key: str, default_rel: str) -> Path:
    val = os.getenv(env_key)
    if val:
        return Path(val).expanduser().resolve()
    return (BASE_DIR / default_rel).resolve()


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-r1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")

DOC_DIR = _path("DOC_DIR", "documents")
PERSIST_DIR = _path("PERSIST_DIR", "data/chroma_db")
MANIFEST_PATH = _path("MANIFEST_PATH", "data/file_manifest.json")
MODELS_DIR = _path("MODELS_DIR", "models")
VOSK_MODEL_NAME = os.getenv("VOSK_MODEL_NAME", "vosk-model-small-cn-0.22")
VOSK_MODEL_PATH = MODELS_DIR / VOSK_MODEL_NAME

COLLECTION_NAME = os.getenv("COLLECTION_NAME", "my_knowledge")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
OVERLAP = int(os.getenv("OVERLAP", "50"))

TOP_K = int(os.getenv("TOP_K", "3"))
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "3"))
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))