import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    PERSIST_DIR, COLLECTION_NAME, TOP_K, MAX_HISTORY_TURNS,
    SAMPLE_RATE, VOSK_MODEL_PATH, HOST, PORT,
)

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse

import chromadb
import ollama
from vosk import Model as VoskModel, KaldiRecognizer
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from build_index import build_index

if not VOSK_MODEL_PATH.exists():
    print(f"[错误] Vosk 模型不存在: {VOSK_MODEL_PATH}")
    print("请先运行: python init_project.py")
    sys.exit(1)

print(f"加载 Vosk: {VOSK_MODEL_PATH}")
vosk_model = VoskModel(str(VOSK_MODEL_PATH))

print(f"连接知识库: {PERSIST_DIR}")
chroma_client = chromadb.PersistentClient(path=str(PERSIST_DIR))
ollama_ef = OllamaEmbeddingFunction(url=OLLAMA_URL, model_name=EMBED_MODEL)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME, embedding_function=ollama_ef
)
print(f"当前片段数: {collection.count()}")

if collection.count() == 0:
    print("知识库为空，尝试自动构建...")
    try:
        build_index(verbose=True)
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME, embedding_function=ollama_ef
        )
    except Exception as e:
        print(f"自动构建失败: {e}")

ollama_client = ollama.AsyncClient(host=OLLAMA_URL)
app = FastAPI(title="本地知识库问答助手")
sessions = {}


def get_history(sid):
    return sessions.setdefault(sid, [])


def trim_history(sid):
    h = sessions[sid]
    if len(h) > MAX_HISTORY_TURNS * 2:
        sessions[sid] = h[-MAX_HISTORY_TURNS * 2:]


def build_rag_message(query, hits):
    context = "\n\n".join(
        f"[片段{i + 1}] {doc}" for i, (doc, meta, dist) in enumerate(hits)
    )
    return f"""请严格依据下面提供的资料回答问题。

规则：
1. 只使用资料中的信息回答，不要编造资料之外的内容。
2. 如果资料中没有相关信息，直接回答“根据现有资料无法回答这个问题”。
3. 回答要简洁、准确，使用中文。
4. 不要提及“片段”“资料编号”等字样，直接自然地回答。
5. 如果问题中有指代（如“它”“这个”），结合之前的对话理解所指对象。

资料：
{context}

问题：{query}
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((ROOT / "code" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/config")
async def api_config():
    return {
        "chat_model": CHAT_MODEL,
        "embed_model": EMBED_MODEL,
        "knowledge_count": collection.count(),
        "top_k": TOP_K,
    }


@app.post("/api/reindex")
async def api_reindex():
    global collection
    try:
        count = build_index(verbose=False)
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME, embedding_function=ollama_ef
        )
        return {"ok": True, "count": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/transcribe")
async def api_transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    recognizer.SetWords(True)
    texts = []
    step = 4000
    for i in range(0, len(data), step):
        if recognizer.AcceptWaveform(data[i:i + step]):
            r = json.loads(recognizer.Result())
            if r.get("text"):
                texts.append(r["text"])
    r = json.loads(recognizer.FinalResult())
    if r.get("text"):
        texts.append(r["text"])
    return {"text": "".join(texts).strip()}


@app.post("/api/clear")
async def api_clear(session_id: str = "default"):
    sessions[session_id] = []
    return {"ok": True}


@app.post("/api/ask")
async def api_ask(request: Request):
    body = await request.json()
    query = (body.get("query") or "").strip()
    sid = body.get("session_id", "default")
    if not query:
        return {"error": "empty query"}

    res = collection.query(query_texts=[query], n_results=TOP_K)
    hits = list(zip(res["documents"][0], res["metadatas"][0], res["distances"][0]))
    dist_str = ", ".join(f"{d:.4f}" for _, _, d in hits)

    history = get_history(sid)
    messages = list(history)
    messages.append({"role": "user", "content": build_rag_message(query, hits)})

    async def generate():
        full = []
        try:
            yield f"data: {json.dumps({'type': 'meta', 'distances': dist_str})}\n\n"
            async for chunk in await ollama_client.chat(
                model=CHAT_MODEL, messages=messages, stream=True
            ):
                if await request.is_disconnected():
                    break
                content = chunk.get("message", {}).get("content") or ""
                if content:
                    full.append(content)
                    yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"

            answer = "".join(full).strip()
            if answer and not await request.is_disconnected():
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": answer})
                trim_history(sid)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except asyncio.CancelledError:
            print("[中断] 客户端断开，停止生成")
            raise

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    print(f"启动服务: http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)