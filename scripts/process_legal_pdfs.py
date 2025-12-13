import os
import sys
import time
import json
import re
from datetime import datetime
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
from app.database import SessionLocal, Base, engine
from app.models import Document, Entity, EntityRelationship
from app.pdf_processor import extract_text_from_pdf, chunk_text

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
Base.metadata.create_all(bind=engine)

LEGAL_FOLDER = "legal"
MODEL_NAME = "gemini-2.5-flash"

def clean_json_string(json_str: str) -> str:
    if not json_str:
        return "{}"
        
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
        
    json_str = re.sub(r'//.*', '', json_str)
    
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    return json_str.strip()

def validate_and_fix_json(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {"الكيانات": {}, "العلاقات": []}
        
    if "الكيانات" not in data or not isinstance(data["الكيانات"], dict):
        data["الكيانات"] = {}
        
    if "العلاقات" not in data or not isinstance(data["العلاقات"], list):
        data["العلاقات"] = []
        
    return data

def process_chunk_with_gemini(chunk_text: str, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
    prompt = f"""
You are an expert legal AI. Extract entities and relationships from this text chunk (Part {chunk_index+1}/{total_chunks}).

**Entities to Extract:**
- رقم_القضية (case_number)
- اسم_المحكمة (court_name)
- تاريخ_الحكم (judgment_date)
- المدعي (plaintiff) - array
- المدعى_عليه (defendant) - array
- القاضي (judge) - array
- المحامي_المدعي (plaintiff_lawyer) - array
- محامي_المدعى_عليه (defendant_lawyer) - array
- الشهود (witnesses) - array
- الخبراء (experts) - array
- المواد_القانونية (legal_articles) - array
- الحكم (decision)
- منطوق_الحكم (verdict)
- الأسباب (reasoning)

**Relationships:**
Extract relationships between entities (e.g., "represents", "against", "witness_for").
Format: {{"من": "entity1", "نوع_العلاقة": "type", "إلى": "entity2"}}

**Rules:**
1. Return VALID JSON only.
2. Keys: "الكيانات" (Entities), "العلاقات" (Relationships).
3. If no data found, return empty arrays/objects.
4. Do NOT include markdown formatting.

Text:
{chunk_text}
"""
    
    max_retries = 10
    wait_time = 30
    
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            
            raw_text = getattr(response, "text", "")
            cleaned_text = clean_json_string(raw_text)
            
            try:
                data = json.loads(cleaned_text)
                return validate_and_fix_json(data)
            except json.JSONDecodeError:
                msg = f"JSON Decode Error in chunk {chunk_index+1} (Attempt {attempt+1})"
                print(f"    {msg}")
                with open("processing_errors.log", "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now()} - {msg}\n")
                    
                if attempt == max_retries - 1:
                    return {"الكيانات": {}, "العلاقات": []}
                
        except Exception as e:
            msg = f"Gemini Error in chunk {chunk_index+1} (Attempt {attempt+1}): {e}"
            print(f"    {msg}")
            with open("processing_errors.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} - {msg}\n")
                
            if "429" in str(e):
                print(f"    Rate limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
                wait_time *= 1.5 
            else:
                time.sleep(5)
                
    return {"الكيانات": {}, "العلاقات": []}

def merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged_entities = {}
    merged_relationships = []
    
    for res in results:
        entities = res.get("الكيانات", {})
        for key, value in entities.items():
            if not value:
                continue
                
            if key not in merged_entities:
                merged_entities[key] = value
            else:
                if isinstance(merged_entities[key], list) and isinstance(value, list):
                    merged_entities[key].extend(value)
                    try:
                        merged_entities[key] = list(set(merged_entities[key]))
                    except TypeError:
                        pass 
                elif isinstance(merged_entities[key], str) and isinstance(value, str):
                    if len(value) > len(merged_entities[key]):
                         merged_entities[key] = value
        
        relationships = res.get("العلاقات", [])
        merged_relationships.extend(relationships)
        
    return {"الكيانات": merged_entities, "العلاقات": merged_relationships}

def save_to_db(filename: str, file_path: str, raw_text: str, data: Dict[str, Any]):
    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.filename == filename).first()
        if existing:
            print(f"    Document {filename} already exists. Skipping save.")
            db.close()
            return

        doc = Document(
            filename=filename,
            file_path=file_path,
            raw_text=raw_text,
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
                
        db.commit()
        print(f"    Saved to DB: {filename} (ID: {doc.id})")
        
    except Exception as e:
        print(f"    DB Error: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    print("="*60)
    print("Robust PDF Processor (Chunking + Merging)")
    print("="*60)
    
    if not os.path.exists(LEGAL_FOLDER):
        print(f"Folder '{LEGAL_FOLDER}' not found.")
        return
        
    pdf_files = [f for f in os.listdir(LEGAL_FOLDER) if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDFs")
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file}")
        pdf_path = os.path.join(LEGAL_FOLDER, pdf_file)
        
        text = extract_text_from_pdf(pdf_path)
        if not text:
            print("    Failed to extract text")
            continue
            
        chunks = chunk_text(text, chunk_size=1000)
        print(f"    Split into {len(chunks)} chunks")
        
        chunk_results = []
        for i, chunk in enumerate(chunks):
            print(f"    Processing chunk {i+1}/{len(chunks)}...")
            result = process_chunk_with_gemini(chunk, i, len(chunks))
            chunk_results.append(result)
            
        final_data = merge_results(chunk_results)
        print(f"    Merged data: {len(final_data['الكيانات'])} entity fields, {len(final_data['العلاقات'])} relationships")
        
        save_to_db(pdf_file, pdf_path, text, final_data)
        
    print("\nAll Done!")

if __name__ == "__main__":
    main()
