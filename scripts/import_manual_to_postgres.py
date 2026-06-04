import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Document, Entity, EntityRelationship

def parse_concatenated_json(file_path):
    """
    Parses a file containing multiple JSON objects (not in a JSON array).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    decoder = json.JSONDecoder()
    pos = 0
    results = []
    
    while pos < len(content):
        while pos < len(content) and content[pos].isspace():
            pos += 1
        
        if pos >= len(content):
            break
            
        try:
            obj, index = decoder.raw_decode(content, pos)
            results.append(obj)
            pos = index
        except json.JSONDecodeError as e:
            print(f"Failed to decode at position {pos}: {e}")
            break
            
    return results

def main():
    load_dotenv()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_file = os.path.join(base_dir, "regex_extracted_data.json")
    
    print(f"Reading data from: {json_file}")
    data_objects = parse_concatenated_json(json_file)
    print(f"Found {len(data_objects)} cases in the JSON file.")
    
    db = SessionLocal()
    
    try:
        from sqlalchemy import text
        db.execute(text("SELECT setval('documents_id_seq', (SELECT MAX(id) FROM documents));"))
        db.execute(text("SELECT setval('entities_id_seq', (SELECT MAX(id) FROM entities));"))
        db.execute(text("SELECT setval('entity_relationships_id_seq', (SELECT MAX(id) FROM entity_relationships));"))
        db.commit()
    except Exception as e:
        print("Note: Sequence update skipped or failed:", e)
        db.rollback()
        
    inserted_count = 0
    skipped_count = 0
    
    try:
        for idx, item in enumerate(data_objects):
            entities_data = item.get("الكيانات", {})
            relationships_data = item.get("العلاقات", [])
            
            case_number = entities_data.get("رقم_القضية")
            
            if case_number:
                exists = db.query(Entity).filter(Entity.case_number == case_number).first()
                if exists:
                    print(f"Skipping case (already in DB)...")
                    skipped_count += 1
                    continue
            
            print(f"Inserting case index {idx}...")
            
            safe_filename = f"manual_import_{case_number.replace('/', '_')}.pdf" if case_number else f"manual_import_unknown_{idx}.pdf"
            doc = Document(
                filename=safe_filename,
                file_path="manual",
                status="processed",
                raw_text="Manual Data Entry"
            )
            db.add(doc)
            db.flush() 
            
            entity = Entity(
                document_id=doc.id,
                case_number=case_number,
                court_name=entities_data.get("اسم_المحكمة"),
                judgment_date=entities_data.get("تاريخ_الحكم"),
                case_type=entities_data.get("نوع_النقض"),
                plaintiff=entities_data.get("المدعي", []),
                defendant=entities_data.get("المدعى_عليه", []),
                judge=entities_data.get("القاضي", []),
                plaintiff_lawyer=entities_data.get("محامي_المدعي", []),
                defendant_lawyer=entities_data.get("محامي_المدعى_عليه", []),
                witnesses=entities_data.get("الشهود", []),
                experts=entities_data.get("الخبراء", []),
                legal_articles=entities_data.get("المواد_القانونية", []),
                verdict=entities_data.get("الحكم"),
                decision=entities_data.get("منطوق_الحكم"),
                reasoning=entities_data.get("الأسباب"),
                raw_entities=entities_data
            )
            db.add(entity)
            
            for rel in relationships_data:
                db_rel = EntityRelationship(
                    document_id=doc.id,
                    from_entity=rel.get("من"),
                    relationship_type=rel.get("نوع_العلاقة"),
                    to_entity=rel.get("إلى")
                )
                db.add(db_rel)
                
            inserted_count += 1
            
        db.commit()
        print(f"\nImport completed. Inserted: {inserted_count}, Skipped (duplicate): {skipped_count}")
        
    except Exception as e:
        db.rollback()
        print(f"Failed to import data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
