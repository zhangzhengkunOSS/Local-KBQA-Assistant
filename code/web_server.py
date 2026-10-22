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

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
import ollama

from config import OLLAMA_URL, CHAT_MODEL, TOP_K, MAX_HISTORY_TURNS, HOST, PORT
from rag_engine import RAGEngine
from voice_handler import VoiceHandler

print("初始化 RAG 引擎...")
rag = RAGEngine()
print(f"当前知识库片段数: {rag.collection.count()}")

if rag.collection.count() == 0:
    print("知识库为空，尝试自动构建...")
    try:
        rag.build_index(verbose=True)
    except Exception as e:
        print(f"自动构建失败: {e}")

print("初始化语音引擎...")
voice = VoiceHandler()

ollama_client = ollama.AsyncClient(host=OLLAMA_URL)
app = FastAPI(title="本地知识库问答助手")
sessions = {}

def get_history(sid):
    return sessions.setdefault(sid, [])

def trim_history(sid):
    h = sessions[sid]
    if len(h) > MAX_HISTORY_TURNS * 2:
        sessions[sid] = h[-MAX_HISTORY_TURNS * 2:]

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((ROOT / "code" / "index.html").read_text(encoding="utf-8"))

@app.get("/api/config")
async def api_config():
    return {
        "chat_model": CHAT_MODEL,
        "embed_model": "bge-m3",  # 可从 config 引入
        "knowledge_count": rag.collection.count(),
        "top_k": TOP_K,
    }

@app.post("/api/reindex")
async def api_reindex():
    try:
        count = rag.build_index(verbose=False)
        return {"ok": True, "count": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/transcribe")
async def api_transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    text = voice.transcribe(data)
    return {"text": text}

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

    hits = rag.retrieve(query, k=TOP_K)
    dist_str = ", ".join(f"{d:.4f}" for _, _, d in hits)

    history = get_history(sid)
    messages = list(history)
    messages.append({"role": "user", "content": rag.build_prompt(query, hits)})

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