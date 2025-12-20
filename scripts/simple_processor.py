import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
import json
from app.database import SessionLocal, Base, engine
from app.models import Document, Entity, EntityRelationship
from app.pdf_processor import extract_text_from_pdf
from datetime import datetime

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
Base.metadata.create_all(bind=engine)

def process_one_pdf(pdf_path, filename):
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")
    
    print("Step 1: Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("Failed to extract text")
        return False
    print(f"Extracted {len(text)} characters")
    
    print("\nStep 2: Sending to Gemini AI (Full Extraction)...")
    
    prompt = f"""
You are an advanced legal information extraction assistant specializing in Arabic court documents.

Your task is to extract CORE entities and their relationships from the provided legal text.

Extract ONLY the following entities (if present):

**Core Case Information:**
- رقم_القضية (case_number)
- اسم_المحكمة (court_name)
- تاريخ_الحكم (judgment_date)

**Parties Involved:**
- المدعي (plaintiff) - can be multiple
- المدعى_عليه (defendant) - can be multiple
- القاضي (judge) - can be multiple

**Relationships:**
Extract ALL relationships between entities in the following format:
- من (from_entity)
- نوع_العلاقة (relationship_type) - e.g., "يمثل" (represents), "ضد" (against), "شاهد_لصالح" (witness_for), "قاضي_في" (judge_in), "استند_إلى" (based_on), "حكم_بـ" (ruled_with), etc.
- إلى (to_entity)

**IMPORTANT:**
1. Use Arabic for all field names and values
2. If an entity has multiple values, use an array
3. Return ONLY valid JSON with two main keys: "الكيانات" (entities) and "العلاقات" (relationships)
4. No explanations, no markdown, just pure JSON

Court Text:
{text[:5000]}  # Truncated to 5k chars to be safe

Expected JSON structure:
{{
  "الكيانات": {{
    "رقم_القضية": "...",
    "اسم_المحكمة": "...",
    ...
  }},
  "العلاقات": [
    {{
      "من": "entity1",
      "نوع_العلاقة": "relationship_type",
      "إلى": "entity2"
    }},
    ...
  ]
}}
"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            response_text = getattr(response, "text", None) or str(response)
            
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            print(f"Got response from Gemini")
            
            parsed = json.loads(response_text)
            print(f"Parsed JSON successfully")
            
            entities_data = parsed.get("الكيانات", parsed if not parsed.get("العلاقات") else {})
            relationships_data = parsed.get("العلاقات", [])
            
            if not isinstance(relationships_data, list):
                relationships_data = []
                
            print(f"    Extracted {len(entities_data)} entity types")
            print(f"    Extracted {len(relationships_data)} relationships")
            break 
            
        except Exception as e:
            print(f"Error with Gemini (Attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                with open("error_log.txt", "w", encoding="utf-8") as f:
                    f.write(f"Gemini Error: {str(e)}")
                return False
            print(f"    Waiting 60 seconds before retry...")
            import time
            time.sleep(60) 
    
    print("\nStep 3: Saving to database...")
    db = SessionLocal()
    
    try:
        document = Document(
            filename=filename,
            file_path=pdf_path,
            raw_text=text,
            status="processed",
            processed_date=datetime.utcnow()
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        print(f"Saved document (ID: {document.id})")
        
        entity = Entity(
            document_id=document.id,
            case_number=entities_data.get("رقم_القضية"),
            court_name=entities_data.get("اسم_المحكمة"),
            judgment_date=entities_data.get("تاريخ_الحكم"),
            session_date=entities_data.get("تاريخ_الجلسة"),
            case_type=entities_data.get("نوع_القضية"),
            case_subject=entities_data.get("موضوع_الدعوى"),
            plaintiff=entities_data.get("المدعي"),
            defendant=entities_data.get("المدعى_عليه"),
            plaintiff_lawyer=entities_data.get("المحامي_المدعي"),
            defendant_lawyer=entities_data.get("محامي_المدعى_عليه"),
            witnesses=entities_data.get("الشهود"),
            experts=entities_data.get("الخبراء"),
            judge=entities_data.get("القاضي"),
            chief_judge=entities_data.get("رئيس_المحكمة"),
            court_members=entities_data.get("أعضاء_الهيئة"),
            court_clerk=entities_data.get("كاتب_الجلسة"),
            legal_articles=entities_data.get("المواد_القانونية"),
            precedents=entities_data.get("الأحكام_السابقة"),
            applied_laws=entities_data.get("القوانين_المطبقة"),
            financial_amounts=entities_data.get("المبالغ_المالية"),
            properties=entities_data.get("الممتلكات"),
            compensations=entities_data.get("التعويضات"),
            locations=entities_data.get("الأماكن"),
            important_dates=entities_data.get("التواريخ_المهمة"),
            decision=entities_data.get("الحكم"),
            verdict=entities_data.get("منطوق_الحكم"),
            reasoning=entities_data.get("الأسباب"),
            raw_entities=entities_data
        )
        db.add(entity)
        db.commit()
        print(f"Saved entities")
        
        if relationships_data:
            print(f"Saving {len(relationships_data)} relationships...")
            for rel in relationships_data:
                if isinstance(rel, dict):
                    from_ent = rel.get("من")
                    to_ent = rel.get("إلى")
                    if from_ent and to_ent:
                        relationship = EntityRelationship(
                            document_id=document.id,
                            from_entity=str(from_ent),
                            relationship_type=str(rel.get("نوع_العلاقة", "related_to")),
                            to_entity=str(to_ent)
                        )
                        db.add(relationship)
            db.commit()
            print(f"Saved relationships")
        
        db.close()
        print(f"\nSUCCESS! {filename} processed and saved!")
        return True
        
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
        db.close()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SIMPLE PDF PROCESSOR (FULL EXTRACTION)")
    print("="*60)
    
    legal_folder = "legal"
    pdf_files = [f for f in os.listdir(legal_folder) if f.endswith('.pdf')]
    
    print(f"\nFound {len(pdf_files)} PDF files")
    
    if pdf_files:
        pdf_file = pdf_files[0]
        pdf_path = os.path.join(legal_folder, pdf_file)
        
        success = process_one_pdf(pdf_path, pdf_file)
        
        if success:
            print("\n" + "="*60)
            print("DONE! Check database with:")
            print("   python scripts/show_database.py")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("Failed - see error above")
            print("="*60)
    else:
        print("No PDF files found in 'legal' folder")
