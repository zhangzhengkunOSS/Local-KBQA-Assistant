import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    OLLAMA_URL, CHAT_MODEL, EMBED_MODEL,
    VOSK_MODEL_NAME, VOSK_MODEL_PATH, MODELS_DIR, DOC_DIR,
)
from rag_engine import RAGEngine

import ollama

VOSK_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"


def _model_names(resp):
    models = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", []) or []
    names = []
    for m in models:
        if isinstance(m, dict):
            names.append(m.get("name") or m.get("model"))
        else:
            names.append(getattr(m, "name", None) or getattr(m, "model", None))
    return [n for n in names if n]


def check_ollama() -> bool:
    print(f"[1/4] 检查 Ollama 服务 ({OLLAMA_URL})...")
    try:
        ollama.Client(host=OLLAMA_URL).list()
        print("  OK")
        return True
    except Exception as e:
        print(f"  ✗ 无法连接: {e}")
        print("  请先启动 Ollama，并在终端或官网重新运行")
        return False


def ensure_model(name: str, label: str) -> bool:
    print(f"[模型] 检查 {label}: {name}")
    try:
        resp = ollama.Client(host=OLLAMA_URL).list()
        names = _model_names(resp)
        if name in names or f"{name}:latest" in names:
            print("  已存在")
            return True
    except Exception as e:
        print(f"  ✗ 获取列表失败: {e}")
        return False

    print(f"  未找到，自动拉取（大模型可能需要较长时间）...")
    try:
        for progress in ollama.Client(host=OLLAMA_URL).pull(name, stream=True):
            status = progress.get("status", "") if isinstance(progress, dict) else ""
            if status:
                print(f"  {status}", end="\r", flush=True)
        print()
        print("  拉取完成")
        return True
    except Exception as e:
        print(f"  ✗ 拉取失败: {e}")
        print(f"  请手动执行: ollama pull {name}")
        return False


def download_vosk() -> bool:
    print(f"[2/4] 检查 Vosk 语音模型...")
    if VOSK_MODEL_PATH.exists() and any(VOSK_MODEL_PATH.iterdir()):
        print(f"  已存在: {VOSK_MODEL_PATH}")
        return True

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MODELS_DIR / f"{VOSK_MODEL_NAME}.zip"
    print(f"  下载: {VOSK_URL}")
    try:
        urllib.request.urlretrieve(VOSK_URL, zip_path)
        print("  解压...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(MODELS_DIR)
        zip_path.unlink()
        print(f"  完成: {VOSK_MODEL_PATH}")
        return True
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        print(f"  请手动下载后解压到 {MODELS_DIR}")
        return False


def init_kb() -> bool:
    print(f"[3/4] 初始化知识库...")
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in DOC_DIR.iterdir() if p.suffix.lower() in (".txt", ".md")]
    if not files:
        print(f"  ⚠ 文档目录为空: {DOC_DIR}")
        print(f"  请放入 .txt 或 .md 文件后重启")
        return False

    try:
        rag = RAGEngine()
        rag.build_index(verbose=True)
        return True
    except Exception as e:
        print(f"  ✗ 构建失败: {e}")
        return False


def main() -> int:
    print("=" * 55)
    print("  本地私有知识库语音问答助手 · 初始化")
    print("=" * 55)

    if not check_ollama():
        return 1

    ok_chat = ensure_model(CHAT_MODEL, "对话模型")
    ok_embed = ensure_model(EMBED_MODEL, "嵌入模型")
    ok_vosk = download_vosk()
    ok_kb = init_kb()

    print("[4/4] 汇总")
    checks = [
        ("Ollama 服务", True),
        ("对话模型", ok_chat),
        ("嵌入模型", ok_embed),
        ("Vosk 模型", ok_vosk),
        ("知识库", ok_kb),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")

    if all(ok for _, ok in checks):
        print("\n初始化完成，可以启动: python code/web_server.py")
        return 0
    print("\n请根据上面的 ✗ 项处理后重试")
    return 1


if __name__ == "__main__":
    sys.exit(main())