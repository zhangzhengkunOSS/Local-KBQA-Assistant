import sys
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    DOC_DIR, PERSIST_DIR, MANIFEST_PATH, COLLECTION_NAME,
    OLLAMA_URL, EMBED_MODEL, CHUNK_SIZE, OVERLAP,
)

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            start = 0
            while start < len(para):
                end = start + chunk_size
                chunks.append(para[start:end])
                start = end - overlap
    return chunks


def build_index(verbose: bool = True) -> int:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    PERSIST_DIR.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(PERSIST_DIR))
    ollama_ef = OllamaEmbeddingFunction(url=OLLAMA_URL, model_name=EMBED_MODEL)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ollama_ef
    )

    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    current_files = {}
    for p in sorted(DOC_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            current_files[str(p)] = file_hash(p)

    added = updated = skipped = removed = 0

    for path_str, h in current_files.items():
        old = manifest.get(path_str)
        if old == h:
            skipped += 1
            continue
        if old is not None:
            collection.delete(where={"source": path_str})
            updated += 1
        else:
            added += 1

        with open(path_str, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = split_text(text)
        if not chunks:
            continue

        ids = [f"{Path(path_str).name}::{i}" for i in range(len(chunks))]
        collection.add(
            ids=ids,
            documents=chunks,
            metadatas=[
                {"source": path_str, "chunk_index": i}
                for i in range(len(chunks))
            ],
        )
        if verbose:
            print(f"  {'更新' if old else '新增'} {Path(path_str).name}：{len(chunks)} 片段")

    for path_str in list(manifest.keys()):
        if path_str not in current_files:
            collection.delete(where={"source": path_str})
            del manifest[path_str]
            removed += 1
            if verbose:
                print(f"  删除 {Path(path_str).name}")

    manifest.update(current_files)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"  完成：新增{added} 更新{updated} 跳过{skipped} 删除{removed}")
        print(f"  知识库共 {collection.count()} 条片段")
    return collection.count()


if __name__ == "__main__":
    build_index(verbose=True)