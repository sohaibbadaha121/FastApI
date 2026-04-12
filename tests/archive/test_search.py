import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.vector_store import VectorStoreManager

def main():
    print("Loading Vector Database...\n")
    vector_store = VectorStoreManager()
    
    while True:
        query = input("Enter your legal query (or type 'exit' to quit): ")
        if query.strip() == "":
            continue
        if query.strip().lower() in ['exit', 'quit']:
            break
            
        print("\nSearching for relevant legal documents...\n")
        results = vector_store.search(query, n_results=10)
        
        if not results['documents'][0]:
            print("No results found.")
            continue
            
        for i in range(len(results['documents'][0])):
            doc_text = results['documents'][0][i]
            metadata = results['metadatas'][0][i]
            filename = metadata.get('filename', 'Unknown')
            
            print(f"--- Result {i+1} ---")
            print(f"File: {filename}")
            print(f"Content:\n{doc_text}")
            print("-" * 40 + "\n")

if __name__ == "__main__":
    main()
