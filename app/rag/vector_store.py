import chromadb
import numpy as np
import pickle
import os
import re
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Optional

BM25_CACHE_PATH = "./chroma_db/bm25_cache.pkl"

# Arabic diacritics pattern
_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')
# Common Arabic prefixes to strip for better BM25 matching
_AL_PREFIX = re.compile(r'^(ال|وال|بال|كال|فال|لل)')

def _arabic_tokenize(text: str) -> List[str]:
    """Tokenize Arabic text with light normalization for BM25."""
    # Remove diacritics
    text = _DIACRITICS.sub('', text)
    # Normalize alef variants
    text = re.sub(r'[أإآ]', 'ا', text)
    # Normalize taa marbuta
    text = re.sub(r'ة', 'ه', text)
    words = text.split()
    result = []
    for w in words:
        # Strip definite article and common prefixes
        stripped = _AL_PREFIX.sub('', w)
        if stripped and len(stripped) > 1:
            result.append(stripped)
        elif w and len(w) > 1:
            result.append(w)
    return result

class VectorStoreManager:
    def __init__(self, db_path: str = "./chroma_db", model_name: str = "BAAI/bge-m3"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="legal_documents",
            metadata={"hnsw:space": "cosine"}
        )
        self.encoder = SentenceTransformer(model_name)
        self.encoder.max_seq_length = 512
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_docs: List[str] = []
        self._bm25_ids: List[str] = []
        self._load_bm25_cache()

    # ------------------------------------------------------------------
    # BM25 cache helpers
    # ------------------------------------------------------------------
    def _load_bm25_cache(self):
        if os.path.exists(BM25_CACHE_PATH):
            try:
                with open(BM25_CACHE_PATH, "rb") as f:
                    cache = pickle.load(f)
                self._bm25 = cache["bm25"]
                self._bm25_docs = cache["docs"]
                self._bm25_ids = cache["ids"]
            except Exception:
                self._bm25 = None

    def _save_bm25_cache(self):
        try:
            os.makedirs(os.path.dirname(BM25_CACHE_PATH), exist_ok=True)
            with open(BM25_CACHE_PATH, "wb") as f:
                pickle.dump({
                    "bm25": self._bm25,
                    "docs": self._bm25_docs,
                    "ids": self._bm25_ids
                }, f)
        except Exception as e:
            print(f"[BM25] Could not save cache: {e}")

    def _rebuild_bm25(self):
        """Rebuild BM25 index from all documents in ChromaDB."""
        try:
            all_docs = self.collection.get(include=["documents"])
            docs = all_docs.get("documents", [])
            ids = all_docs.get("ids", [])
            if not docs:
                return
            # Use Arabic-aware tokenizer for better matching
            tokenized = [_arabic_tokenize(d) for d in docs]
            self._bm25 = BM25Okapi(tokenized)
            self._bm25_docs = docs
            self._bm25_ids = ids
            self._save_bm25_cache()
        except Exception as e:
            print(f"[BM25] Could not rebuild index: {e}")

    # ------------------------------------------------------------------
    # Add documents
    # ------------------------------------------------------------------
    def add_documents(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        embeddings = self.encoder.encode(
            chunks, normalize_embeddings=True, convert_to_numpy=True
        ).tolist()
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        # Rebuild BM25 after every ingestion
        self._rebuild_bm25()

    # ------------------------------------------------------------------
    # Hybrid search (BM25 + Vector) with score fusion
    # ------------------------------------------------------------------
    def search(self, query: str, n_results: int = 7) -> Dict[str, Any]:
        # --- 1. Vector search ---
        query_embedding = self.encoder.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True
        ).tolist()
        vector_res = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(n_results * 5, self.collection.count())
        )

        # Collect candidates from vector search
        candidate_ids: List[str] = []
        candidate_docs: List[str] = []
        candidate_metas: List[Dict] = []
        vec_scores: Dict[str, float] = {}

        if vector_res["documents"] and vector_res["documents"][0]:
            for doc, meta, doc_id, dist in zip(
                vector_res["documents"][0],
                vector_res["metadatas"][0],
                vector_res["ids"][0],
                vector_res["distances"][0]
            ):
                # cosine space → distance = 1 - cosine_sim, so similarity = 1 - distance
                vec_scores[doc_id] = 1.0 - float(dist)
                candidate_ids.append(doc_id)
                candidate_docs.append(doc)
                candidate_metas.append(meta)

        # --- 2. BM25 search (if index available) ---
        bm25_scores: Dict[str, float] = {}
        if self._bm25 is not None and self._bm25_docs:
            # Use the same Arabic normalization on the query
            tokenized_query = _arabic_tokenize(query)
            raw_scores = self._bm25.get_scores(tokenized_query)
            # Get top-k BM25 results
            top_k = min(n_results * 5, len(self._bm25_docs))
            top_indices = np.argsort(raw_scores)[::-1][:top_k]
            max_score = raw_scores[top_indices[0]] if top_indices.size > 0 and raw_scores[top_indices[0]] > 0 else 1.0
            for idx in top_indices:
                if raw_scores[idx] <= 0:
                    continue
                doc_id = self._bm25_ids[idx]
                bm25_scores[doc_id] = float(raw_scores[idx]) / max_score  # normalize to [0,1]

                # Add BM25 candidates not already in vector results
                if doc_id not in vec_scores:
                    try:
                        fetched = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
                        if fetched["documents"]:
                            candidate_ids.append(doc_id)
                            candidate_docs.append(fetched["documents"][0])
                            candidate_metas.append(fetched["metadatas"][0])
                    except Exception:
                        pass

        # --- 3. Reciprocal Rank Fusion (RRF) ---
        rrf_scores: Dict[str, float] = {}
        k = 60  # RRF constant

        # Rank vector results
        vec_ranked = sorted(vec_scores.keys(), key=lambda x: vec_scores[x], reverse=True)
        for rank, doc_id in enumerate(vec_ranked):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        # Rank BM25 results
        bm25_ranked = sorted(bm25_scores.keys(), key=lambda x: bm25_scores[x], reverse=True)
        for rank, doc_id in enumerate(bm25_ranked):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        # --- 4. Sort by RRF and return top-n ---
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:n_results]

        # Build a lookup dict from candidates
        id_to_doc = {doc_id: doc for doc_id, doc in zip(candidate_ids, candidate_docs)}
        id_to_meta = {doc_id: meta for doc_id, meta in zip(candidate_ids, candidate_metas)}
        id_to_dist = {doc_id: 1.0 - vec_scores.get(doc_id, 0.5) for doc_id in sorted_ids}

        final_docs = [id_to_doc[i] for i in sorted_ids if i in id_to_doc]
        final_metas = [id_to_meta[i] for i in sorted_ids if i in id_to_meta]
        final_dists = [id_to_dist[i] for i in sorted_ids if i in id_to_doc]
        final_ids = [i for i in sorted_ids if i in id_to_doc]

        return {
            "ids": [final_ids],
            "documents": [final_docs],
            "metadatas": [final_metas],
            "distances": [final_dists]
        }
