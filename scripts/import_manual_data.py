import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Base, engine
from app.models import Document, Entity, EntityRelationship

Base.metadata.create_all(bind=engine)

def import_data(json_file):
    if not os.path.exists(json_file):
        print(f"File not found: {json_file}")
        return

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    print(f"Found {len(data_list)} documents to import")
    
    db = SessionLocal()
    
    try:
        for item in data_list:
            filename = item.get("filename")
            data = item.get("data", {})
            
            print(f"\nImporting: {filename}")
            
            existing = db.query(Document).filter(Document.filename == filename).first()
            if existing:
                print(f"   Document already exists. Deleting old record...")
                db.delete(existing)
                db.commit()
            
            doc = Document(
                filename=filename,
                file_path=f"legal/{filename}", 
                raw_text="Imported manually",
                status="processed",
                processed_date=datetime.utcnow()
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            
            entities = data.get("الكيانات", {})
            relationships = data.get("العلاقات", [])
            
            entity_record = Entity(
                document_id=doc.id,
                case_number=entities.get("رقم_القضية"),
                court_name=entities.get("اسم_المحكمة"),
                judgment_date=entities.get("تاريخ_الحكم"),
                plaintiff=entities.get("المدعي"),
                defendant=entities.get("المدعى_عليه"),
                judge=entities.get("القاضي"),
                plaintiff_lawyer=entities.get("المحامي_المدعي"),
                defendant_lawyer=entities.get("محامي_المدعى_عليه"),
                witnesses=entities.get("الشهود"),
                experts=entities.get("الخبراء"),
                legal_articles=entities.get("المواد_القانونية"),
                decision=entities.get("الحكم"),
                verdict=entities.get("منطوق_الحكم"),
                reasoning=entities.get("الأسباب"),
                raw_entities=entities
            )
            db.add(entity_record)
            
            count_rels = 0
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue
                from_ent = rel.get("من")
                to_ent = rel.get("إلى")
                if from_ent and to_ent:
                    rel_record = EntityRelationship(
                        document_id=doc.id,
                        from_entity=str(from_ent),
                        relationship_type=str(rel.get("نوع_العلاقة", "related_to")),
                        to_entity=str(to_ent)
                    )
                    db.add(rel_record)
                    count_rels += 1
                    
            db.commit()
            print(f"   Imported Entities")
            print(f"   Imported {count_rels} Relationships")
            
        print("\n" + "="*60)
        print("IMPORT COMPLETE!")
        print("="*60)
        
    except Exception as e:
        print(f"Database Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_data("manual_data.json")
