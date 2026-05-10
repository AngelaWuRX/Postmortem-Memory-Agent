"""
Persistent ChromaDB vector store + incident_memory.json sidecar.
ChromaDB handles semantic retrieval; JSON gives a human-readable audit trail.
"""

import json
from pathlib import Path
import chromadb

from agent.parser import MemoryChunk

GENERATED_DIR = Path("generated")
MEMORY_JSON = GENERATED_DIR / "incident_memory.json"
CHROMA_PATH = ".chroma_db"

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_or_create_collection(
            name="postmortem_memory",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def store(chunk: MemoryChunk) -> None:
    col = _get_collection()
    if col.get(ids=[chunk.id])["ids"]:
        return
    col.add(
        ids=[chunk.id],
        documents=[chunk.raw_summary],
        metadatas=[chunk.to_chroma_metadata()],
    )
    _append_to_json(chunk)


def query(text: str, top_k: int = 3) -> list[MemoryChunk]:
    col = _get_collection()
    n = col.count()
    if n == 0:
        return []
    results = col.query(query_texts=[text], n_results=min(top_k, n))
    return [
        MemoryChunk.from_chroma(
            id=results["ids"][0][i],
            metadata=results["metadatas"][0][i],
            document=results["documents"][0][i],
        )
        for i in range(len(results["ids"][0]))
    ]


def all_chunks() -> list[MemoryChunk]:
    col = _get_collection()
    if col.count() == 0:
        return []
    r = col.get()
    return [
        MemoryChunk.from_chroma(id=r["ids"][i], metadata=r["metadatas"][i], document=r["documents"][i])
        for i in range(len(r["ids"]))
    ]


def count() -> int:
    return _get_collection().count()


def _append_to_json(chunk: MemoryChunk) -> None:
    GENERATED_DIR.mkdir(exist_ok=True)
    existing = json.loads(MEMORY_JSON.read_text()) if MEMORY_JSON.exists() else []
    existing.append(chunk.model_dump())
    MEMORY_JSON.write_text(json.dumps(existing, indent=2))
