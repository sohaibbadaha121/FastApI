import sys
import os
import json
import re

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Document, Entity, EntityRelationship
from app.pdf_processor import extract_text_from_pdf

def clean_json_str(json_str):
    # Remove any line that starts with //
    lines = json_str.split('\n')
    cleaned = []
    for line in lines:
        if line.strip().startswith('//'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

def parse_manual_data_robust(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by the separator user used
    # Regex to find: // for <filename>
    # We will iterate through findings
    
    pattern = re.compile(r'//\s*for\s+([^\r\n]+)', re.IGNORECASE)
    matches = list(pattern.finditer(content))
    
    results = {}
    
    for i, match in enumerate(matches):
        filename_raw = match.group(1).strip()
        start_idx = match.end()
        
        # End index is the start of next match or EOF
        if i + 1 < len(matches):
            end_idx = matches[i+1].start()
        else:
            end_idx = len(content)
            
        json_chunk = content[start_idx:end_idx]
        
        # Determine filename
        filename = filename_raw.split()[0] # Take first word e.g. "test.pdf" from "test.pdf file"
        
        # Filename mapping
        if "prepdffile" in filename.lower():
            filename = "PDFPre.pdf"
        elif "test.pdf" in filename.lower():
             filename = "test.pdf"
        elif "test1.pdf" in filename.lower():
             filename = "test1.pdf"
             
        if not filename.endswith('.pdf'):
            filename += ".pdf"
            
        print(f"Found section for: {filename}")
        
        # Extract JSON
        try:
            # Find the outer braces
            json_start = json_chunk.find('{')
            json_end = json_chunk.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                print(f"  ❌ No JSON found for {filename}")
                continue
                
            clean_chunk = json_chunk[json_start:json_end]
            # Remove comments inside just in case, though standard JSON won't have them
            # pure JSON doesn't support comments, but the user might have left some?
            # We'll try loading directly first.
            try:
                data = json.loads(clean_chunk)
                results[filename] = data
                print(f"  ✅ Parsed JSON for {filename}")
            except json.JSONDecodeError as e:
                # Try simple comment stripping //
                clean_chunk = clean_json_str(clean_chunk)
                data = json.loads(clean_chunk)
                results[filename] = data
                print(f"  ✅ Parsed JSON for {filename} (after cleaning)")
                
        except Exception as e:
            print(f"  ❌ Error parsing {filename}: {e}")
            
    return results

def delete_existing_data(db, filename):
    print(f"Checking for existing data for {filename}...")
    doc = db.query(Document).filter(Document.filename == filename).first()
    if doc:
        print(f"  🗑️  Deleting existing document ID: {doc.id}")
        # Delete children manually if cascading is not set up, though usually it should be.
        # Let's be safe and delete children.
        db.query(EntityRelationship).filter(EntityRelationship.document_id == doc.id).delete()
        db.query(Entity).filter(Entity.document_id == doc.id).delete()
        db.delete(doc)
        db.commit()
        print("  ✅ Deleted.")
    else:
        print("  ✨ No existing document found.")

def insert_data(db, filename, data):
    # 1. Get raw text from file system
    legal_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legal")
    pdf_path = os.path.join(legal_dir, filename)
    
    raw_text = ""
    if os.path.exists(pdf_path):
        try:
            raw_text = extract_text_from_pdf(pdf_path)
        except Exception as e:
            print(f"  ⚠️ Could not read PDF text: {e}")
    else:
        # Try to find file case-insensitive
        pass 
        
    print(f"  Inserting data for {filename}...")
    
    # Create Document
    new_doc = Document(
        filename=filename,
        file_path=pdf_path if os.path.exists(pdf_path) else f"legal/{filename}",
        raw_text=raw_text,
        status="processed"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # Parse entities
    ents = data.get("الكيانات", {})
    rels = data.get("العلاقات", [])
    
    if not ents and not rels:
        print("  ⚠️ Empty data for this file.")
    
    # Create Entity record
    # Note: Using .get() for safe access
    entity_record = Entity(
        document_id=new_doc.id,
        case_number=ents.get("رقم_القضية"),
        court_name=ents.get("اسم_المحكمة"),
        judgment_date=ents.get("تاريخ_الحكم"),
        plaintiff=ents.get("المدعي"),
        defendant=ents.get("المدعى_عليه"),
        judge=ents.get("القاضي"),
        plaintiff_lawyer=ents.get("محامي_المدعي"),
        defendant_lawyer=ents.get("محامي_المدعى_عليه"),
        witnesses=ents.get("الشهود"),
        experts=ents.get("الخبراء"),
        legal_articles=ents.get("المواد_القانونية"),
        decision=ents.get("الحكم"),
        verdict=ents.get("منطوق_الحكم"),
        reasoning=ents.get("الأسباب"),
        raw_entities=ents
    )
    db.add(entity_record)
    
    # Create Relationships
    count_rels = 0
    for rel in rels:
        from_e = rel.get("من")
        to_e = rel.get("إلى")
        type_e = rel.get("نوع_العلاقة")
        
        if from_e and to_e:
            r = EntityRelationship(
                document_id=new_doc.id,
                from_entity=str(from_e),
                to_entity=str(to_e),
                relationship_type=str(type_e)
            )
            db.add(r)
            count_rels += 1
            
    db.commit()
    print(f"  ✅ Inserted 1 Entity record and {count_rels} Relationships.")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manual_file = os.path.join(base_dir, "manual_data.json")
    
    if not os.path.exists(manual_file):
        print("manual_data.json not found")
        return

    print("--- Parsing Manual Data ---")
    data_map = parse_manual_data_robust(manual_file)
    
    if not data_map:
        print("No data found!")
        return
        
    db = SessionLocal()
    try:
        for filename, data in data_map.items():
            print(f"\nProcessing {filename}...")
            delete_existing_data(db, filename)
            insert_data(db, filename, data)
    finally:
        db.close()
        
    print("\nDONE.")

if __name__ == "__main__":
    main()
