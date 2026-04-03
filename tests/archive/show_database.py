from database import SessionLocal
from models import Document, Entity, EntityRelationship

db = SessionLocal()

print("\n" + "="*60)
print("DATABASE CONTENTS")
print("="*60)

documents = db.query(Document).all()

print(f"\nTotal Documents: {len(documents)}\n")

for doc in documents:
    print(f"{'─'*60}")
    print(f"Document ID: {doc.id}")
    print(f"Filename: {doc.filename}")
    print(f"Status: {doc.status}")
    print(f"Processed: {doc.processed_date}")
    
    entities = db.query(Entity).filter(Entity.document_id == doc.id).all()
    print(f"\nEntities: {len(entities)}")
    
    if entities:
        entity = entities[0]
        print(f"   رقم القضية: {entity.case_number}")
        print(f"   اسم المحكمة: {entity.court_name}")
        print(f"   المدعي: {entity.plaintiff}")
        print(f"   المدعى عليه: {entity.defendant}")
        print(f"   القاضي: {entity.judge}")
    
    relationships = db.query(EntityRelationship).filter(
        EntityRelationship.document_id == doc.id
    ).all()
    print(f"\nRelationships: {len(relationships)}")
    
    if relationships:
        for i, rel in enumerate(relationships[:3], 1):
            print(f"   {i}. {rel.from_entity} --[{rel.relationship_type}]--> {rel.to_entity}")
        if len(relationships) > 3:
            print(f"   ... and {len(relationships) - 3} more")
    
    print()

print("="*60)
print("ALL DATA SUCCESSFULLY EXTRACTED AND SAVED!")
print("="*60)

db.close()
