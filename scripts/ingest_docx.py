import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.document_loader import DocumentLoader
from app.rag.text_processor import ArabicTextProcessor
from app.rag.vector_store import VectorStoreManager

def extract_doc_context(content: str) -> str:
    # Extract the first 3 non-empty lines for document context/title
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    context_lines = []
    for line in lines[:3]:
        # Stop context extraction if we hit a signature, general date, or article starter
        if any(kw in line for kw in ["رئيس دولة", "رئيس اللجنة", "قررنا", "مادة", "المادة", "ماده", "الماده"]):
            break
        context_lines.append(line)
    
    return " - ".join(context_lines).strip()

def main():
    docs_dir = "./legal_docx"
    
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)
        print(f"Created {docs_dir}. Please place .docx or .txt files there and run again.")
        return

    loader = DocumentLoader(docs_dir)
    vector_store = VectorStoreManager()
    processor = ArabicTextProcessor()

    # Support clearing the collection to avoid duplicate/old format chunks
    if "--clear" in sys.argv:
        print("Clearing existing RAG ChromaDB collection 'legal_documents'...")
        try:
            vector_store.client.delete_collection("legal_documents")
            # Recreate it
            vector_store.collection = vector_store.client.get_or_create_collection(name="legal_documents")
            print("Collection cleared successfully.")
        except Exception as e:
            print(f"Warning: Could not clear collection: {e}")

    raw_docs = loader.load_all_files()
    if not raw_docs:
        print("No .docx or .txt files found in directory.")
        return

    chunks_to_insert = []
    metadatas_to_insert = []
    ids_to_insert = []
    doc_counter = 1

    for doc in raw_docs:
        # Extract title/number context from the original raw content
        doc_context = extract_doc_context(doc["content"])
        normalized_context = processor.normalize(doc_context)
        
        # Normalize and split into articles with context prepended
        normalized_content = processor.normalize(doc["content"])
        articles = processor.split_into_articles(normalized_content, doc_context=normalized_context)
        
        chunk_counter = 1
        for article in articles:
            if not article.strip():
                continue
                
            safe_filename = "".join(x for x in doc["filename"] if x.isalnum() or x in "._-")
            chunk_id = f"{safe_filename}_chunk_{chunk_counter}"
            chunks_to_insert.append(article)
            metadatas_to_insert.append({
                "filename": doc["filename"], 
                "chunk_index": chunk_counter
            })
            ids_to_insert.append(chunk_id)
            
            chunk_counter += 1
            
        doc_counter += 1

    if chunks_to_insert:
        vector_store.add_documents(chunks_to_insert, metadatas_to_insert, ids_to_insert)
        print(f"Successfully inserted {len(chunks_to_insert)} chunks from {len(raw_docs)} files.")

if __name__ == "__main__":
    main()

