import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

class VectorStoreManager:
    def __init__(self, db_path: str = "./chroma_db", model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="legal_documents")
        self.encoder = SentenceTransformer(model_name)

    def add_documents(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        embeddings = self.encoder.encode(chunks, convert_to_numpy=True).tolist()
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        query_embedding = self.encoder.encode([query], convert_to_numpy=True).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results
