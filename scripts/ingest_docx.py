import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.document_loader import DocumentLoader
from app.rag.text_processor import ArabicTextProcessor
from app.rag.vector_store import VectorStoreManager

def main():
    docs_dir = "./legal_docx"
    
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)
        print(f"Created {docs_dir}. Please place .docx files there and run again.")
        return

    loader = DocumentLoader(docs_dir)
    vector_store = VectorStoreManager()
    processor = ArabicTextProcessor()

    raw_docs = loader.load_docx_files()
    if not raw_docs:
        print("No .docx files found in directory.")
        return

    chunks_to_insert = []
    metadatas_to_insert = []
    ids_to_insert = []
    doc_counter = 1

    for doc in raw_docs:
        normalized_content = processor.normalize(doc["content"])
        articles = processor.split_into_articles(normalized_content)
        
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
        print(f"Successfully inserted {len(chunks_to_insert)} chunks.")

if __name__ == "__main__":
    main()
