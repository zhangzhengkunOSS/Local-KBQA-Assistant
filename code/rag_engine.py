import json
import hashlib
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from config import (
    DOC_DIR, PERSIST_DIR, MANIFEST_PATH, COLLECTION_NAME,
    OLLAMA_URL, EMBED_MODEL, CHUNK_SIZE, OVERLAP,
)


class RAGEngine:
    def __init__(self):
        PERSIST_DIR.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(PERSIST_DIR))
        self.ollama_ef = OllamaEmbeddingFunction(url=OLLAMA_URL, model_name=EMBED_MODEL)

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=self.ollama_ef
        )

    def _file_hash(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()

    def _split_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP):
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

    def build_index(self, verbose: bool = True) -> int:
        DOC_DIR.mkdir(parents=True, exist_ok=True)

        manifest = {}
        if MANIFEST_PATH.exists():
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)

        current_files = {}
        for p in sorted(DOC_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in (".txt", ".md"):
                current_files[str(p)] = self._file_hash(p)

        added = updated = skipped = removed = 0

        for path_str, h in current_files.items():
            old = manifest.get(path_str)
            if old == h:
                skipped += 1
                continue
            if old is not None:
                self.collection.delete(where={"source": path_str})
                updated += 1
            else:
                added += 1

            with open(path_str, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = self._split_text(text)
            if not chunks:
                continue

            ids = [f"{Path(path_str).name}::{i}" for i in range(len(chunks))]
            self.collection.add(
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
                self.collection.delete(where={"source": path_str})
                del manifest[path_str]
                removed += 1
                if verbose:
                    print(f"  删除 {Path(path_str).name}")

        manifest.update(current_files)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        if verbose:
            print(f"  完成：新增{added} 更新{updated} 跳过{skipped} 删除{removed}")
            print(f"  知识库共 {self.collection.count()} 条片段")
        return self.collection.count()

    def retrieve(self, query: str, k: int = 3):
        res = self.collection.query(query_texts=[query], n_results=k)
        return list(zip(res["documents"][0], res["metadatas"][0], res["distances"][0]))

    def build_prompt(self, query: str, hits: list) -> str:
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