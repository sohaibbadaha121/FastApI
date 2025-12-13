import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Document, Entity, EntityRelationship
import json

def view_all_documents():
    db = SessionLocal()
    
    print("\n" + "=" * 60)
    print("ALL DOCUMENTS IN DATABASE")
    print("=" * 60)
    
    documents = db.query(Document).all()
    
    if not documents:
        print("\nNo documents found in database")
        print("Run 'python process_legal_pdfs.py' to process PDFs first")
        db.close()
        return
    
    print(f"\nTotal Documents: {len(documents)}\n")
    
    for doc in documents:
        print(f"{'─' * 60}")
        print(f"ID: {doc.id}")
        print(f"Filename: {doc.filename}")
        print(f"Upload Date: {doc.upload_date}")
        print(f"Status: {doc.status}")
        print(f"Text Length: {len(doc.raw_text) if doc.raw_text else 0} characters")
    
    print(f"{'─' * 60}\n")
    db.close()

def view_document_details(document_id):
    db = SessionLocal()
    
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        print(f"\nDocument with ID {document_id} not found!")
        db.close()
        return
    
    print("\n" + "=" * 60)
    print(f"DOCUMENT DETAILS - ID: {document_id}")
    print("=" * 60)
    
    print(f"\nFilename: {document.filename}")
    print(f"Upload Date: {document.upload_date}")
    print(f"Processed Date: {document.processed_date}")
    print(f"Status: {document.status}")
    
    entities = db.query(Entity).filter(Entity.document_id == document_id).all()
    
    print("\n" + "─" * 60)
    print("EXTRACTED ENTITIES")
    print("─" * 60)
    
    if entities:
        for entity in entities:
            print(f"\nEntity ID: {entity.id}")
            
            if entity.case_number:
                print(f"   رقم القضية: {entity.case_number}")
            if entity.court_name:
                print(f"   اسم المحكمة: {entity.court_name}")
            if entity.judgment_date:
                print(f"   تاريخ الحكم: {entity.judgment_date}")
            if entity.plaintiff:
                print(f"   المدعي: {entity.plaintiff}")
            if entity.defendant:
                print(f"   المدعى عليه: {entity.defendant}")
            if entity.judge:
                print(f"   القاضي: {entity.judge}")
            if entity.legal_articles:
                print(f"   المواد القانونية: {entity.legal_articles}")
            if entity.decision:
                print(f"   الحكم: {entity.decision}")
            if entity.verdict:
                print(f"   منطوق الحكم: {entity.verdict}")
            
            if entity.raw_entities:
                print(f"\n   All Extracted Entities:")
                for key, value in entity.raw_entities.items():
                    if value:
                        print(f"      • {key}: {value}")
    else:
        print("\nNo entities found for this document")
    
    relationships = db.query(EntityRelationship).filter(
        EntityRelationship.document_id == document_id
    ).all()
    
    print("\n" + "─" * 60)
    print("EXTRACTED RELATIONSHIPS")
    print("─" * 60)
    
    if relationships:
        print(f"\nTotal Relationships: {len(relationships)}\n")
        for i, rel in enumerate(relationships, 1):
            print(f"{i}. {rel.from_entity} --[{rel.relationship_type}]--> {rel.to_entity}")
    else:
        print("\nNo relationships found for this document")
    
    print("\n" + "=" * 60)
    db.close()

def main():
    print("\n" + "=" * 60)
    print("LEGAL DOCUMENTS VIEWER")
    print("=" * 60)
    
    while True:
        print("\nMenu:")
        print("  1. View all documents")
        print("  2. View specific document details")
        print("  3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            view_all_documents()
        
        elif choice == "2":
            try:
                doc_id = int(input("\nEnter document ID: ").strip())
                view_document_details(doc_id)
            except ValueError:
                print("\nInvalid ID! Please enter a number.")
        
        elif choice == "3":
            print("\nGoodbye!")
            break
        
        else:
            print("\nInvalid choice! Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
