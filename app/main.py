
import os
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import json
import shutil
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Document, Entity, EntityRelationship
from typing import Optional, List
from sqlalchemy import or_, cast, String
from app.pdf_processor import extract_text_from_pdf
from openai import OpenAI

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI")
genai.configure(api_key=gemini_api_key)

# OpenRouter Configuration
openrouter_api_key = (
    os.getenv("OPENROUTER_API_KEY") or 
    os.getenv("OPENROUTER_KEY") or 
    os.getenv("OPENROUTER") or
    os.getenv("OPEN_ROUTER") or
    os.getenv("OPEN_ROUTER_API_KEY")
)
or_client = None
if openrouter_api_key:
    or_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_api_key
    )
OR_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-4b-it:free")

# Create tables if they don't exist
from app.models import Base
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    lawText: str


class DbQueryRequest(BaseModel):
    query: Optional[str] = None
    case_number: Optional[str] = None
    court_name: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    judge: Optional[str] = None
    verdict: Optional[str] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/extract")
async def extract_entities(request: ExtractRequest):
    law_text = request.lawText
    prompt = f"""
You are an advanced legal information extraction assistant specializing in Arabic court documents.
Your task is to extract ALL possible entities and their relationships from the provided legal text.
(Prompt truncated for brevity, same as before...)
Court Text:
{law_text}
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", "")
        
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
            return {
                "entities": parsed.get("الكيانات", parsed),
                "relationships": parsed.get("العلاقات", [])
            }
        except Exception as parse_error:
            return {"entities_raw": text, "parse_error": str(parse_error)}

    except Exception as e:
        return {"error": str(e)}


@app.post("/api/ask")
async def ask_question(file: UploadFile = File(None), question: str = Form(...)):
    """
    Revised endpoint to handle PDF upload OR Database RAG Queries.
    """
    if file is None:
        # -------------------------------------------------------------
        # Path 1: Global RAG Search over all Legal Word Docs
        # -------------------------------------------------------------
        try:
            from app.rag.vector_store import VectorStoreManager
            
            vector_store = VectorStoreManager()
            results = vector_store.search(question, n_results=10)
            
            if not results['documents'] or not results['documents'][0]:
                return {"answer": "لم أتمكن من العثور على أية تشريعات مرتبطة بسؤالك."}
                
            # Combine the chunks into a unified context string
            context_text = "\n\n".join([
                f"--- نص قانوني من تشريع: {meta.get('filename', 'Unknown')} ---\n{doc}"
                for doc, meta in zip(results['documents'][0], results['metadatas'][0])
            ])
            
            prompt = f"""
أنت مستشار قانوني فلسطيني ذكي ومحترف. 
الرجاء الإجابة على سؤال المستخدم بناءً **فقط** على النصوص القانونية التالية المستخرجة من التشريعات الرسمية:

النصوص القانونية:
{context_text}

سؤال المستخدم:
{question}

طريقة الإجابة الإلزامية:
1. أجب باللغة العربية الفصحى بشكل دقيق ومباشر.
2. اعتمد حصرياً على النصوص المرفقة، ولا تؤلف أي قوانين أو عقوبات من خارجها.
3. اُذكر اسم التشريع الذي اعتمدت عليه لتعزيز موثوقية جوابك إن أمكن.
4. رتب إجابتك في نقاط واضحة (Bullet points) لتسهيل القراءة.
5. أعطِ الإجابة مباشرة وفوراً، ولا تبدأ أبداً بعبارات مثل "بناءً على النصوص" أو "بصفتي مستشار" أو ختام بـ "هل تحتاج شيئاً آخر".
"""
            # Using Gemini 2.5 Flash as requested
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            
            return {
                "answer": response.text,
                "sources": list(set([m.get("filename") for m in results['metadatas'][0]]))
            }
        except Exception as e:
            return {"error": f"Error performing RAG search: {str(e)}"}

    else:
        # -------------------------------------------------------------
        # Path 2: Explicit PDF Upload QA (Previous Logic)
        # -------------------------------------------------------------
        temp_path = f"temp_{file.filename}"
        
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            law_text = extract_text_from_pdf(temp_path)
            
            if not law_text:
                return {"error": "Could not extract text from the PDF file."}

            if not or_client:
                return {"error": "OpenRouter API key is not configured. Please check your .env file."}

            prompt = f"""
أنت خبير قانوني متخصص في القضاء الفلسطيني.
النص التالي مستخرج آليًا من ملف PDF وقد يحتوي على أخطاء OCR مثل:
- استبدال بعض الحروف (مثال: "ثن" بدل "ال")
- أخطاء في أسماء الأشخاص أو المصطلحات القانونية
مهمتك هي:
1. تصحيح هذه الأخطاء ذهنيًا دون الإشارة إليها صراحة.
2. فهم النص في سياقه القانوني الصحيح.
3. الالتزام حصريًا بما ورد في النص دون إضافة وقائع أو افتراضات.

تعليمات إلزامية:
- لا تفترض وجود ضرر أو تعويض أو مسؤولية إلا إذا ورد ذلك صراحة في النص.
- لا تضف أطرافًا أو وقائع غير مذكورة.
- إن كان النص غير كافٍ للإجابة، صرّح بذلك بوضوح.
- طبّق المبادئ القانونية الفلسطينية فقط.

النص القانوني المستخرج:
{law_text}

سؤال المستخدم:
{question}

طريقة الإجابة:
- أجب باللغة العربية الفصحى.
- قدّم إجابة قانونية موجزة، دقيقة، ومنضبطة.
- إن أمكن، لخّص النتيجة النهائية للحكم أو القاعدة القانونية المستخلصة.
"""
            messages = [{"role": "user", "content": prompt}]
            
            response = or_client.chat.completions.create(
                model=OR_MODEL,
                messages=messages
            )
            
            answer_text = response.choices[0].message.content
            
            return {
                "answer": answer_text,
                "filename": file.filename,
                "text_length": len(law_text)
            }

        except Exception as e:
            return {"error": f"Error processing PDF: {str(e)}"}
        
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass


@app.post("/api/db-query")
async def query_database(request: DbQueryRequest):

    has_specific_fields = any([
        request.case_number, request.court_name, 
        request.plaintiff, request.defendant, 
        request.judge, request.verdict
    ])


    is_json_query = request.query and request.query.strip().startswith("{")
    
    if not has_specific_fields and not is_json_query and request.query:
        # ---------------------------------------------------------
        # Path 1: Natural Language Query -> LLM -> SQL
        # ---------------------------------------------------------
        try:
            from app.chat_utils import get_sql_from_llm, execute_sql
            
            print(f"[INFO] Processing NLQ: {request.query}")
            
            # 1. Generate SQL
            sql = get_sql_from_llm(request.query)
            if not sql:
                return {"answer": "Could not generate a database query for your question. (Check API Key or Logs)"}
            
            print(f"[INFO] Generated SQL: {sql}")
            
            # 2. Execute & Filter
            results = execute_sql(sql, request.query)
            
            if "error" in results:
                return {"answer": f"Database error: {results['error']}"}
            
            if results.get("count", 0) == 0:
                answer_text = "No records found matching your question."
                return {"answer": answer_text}
                
            data = results.get("data", [])
            summary = results.get("summary", None)  # Get summary if available (from COUNT queries)
            
            # Define essential fields to return (filter out verbose fields)
            essential_fields = [
                "case_number", "court_name", "judgment_date", 
                "plaintiff", "defendant", "judge", 
                "verdict", "decision"
            ]

            mapped_data = []
            for row in data:
                item = dict(row)
                clean_item = {"source_document": item.get("document_id")}
                for k, v in item.items():
                    # Skip technical/verbose fields
                    if k in ["raw_entities", "created_at", "id", "document_id", "reasoning", 
                             "legal_articles", "plaintiff_lawyer", "defendant_lawyer",
                             "witnesses", "experts", "chief_judge", "court_members", 
                             "court_clerk", "precedents", "applied_laws", "financial_amounts",
                             "properties", "compensations", "locations", "important_dates",
                             "session_date", "case_type", "case_subject"]:
                        continue
                    
                    # Skip null/empty values
                    if v in ["null", None, "", []]: 
                        continue
                    
                    # Parse JSON strings
                    if isinstance(v, str) and v.startswith("["):
                        try:
                            parsed = json.loads(v)
                            if parsed: clean_item[k] = parsed
                            continue
                        except: pass
                    
                    clean_item[k] = v
                
                if "relationships" not in clean_item: 
                    clean_item["relationships"] = []
                    
                mapped_data.append(clean_item)
            
            # If summary exists (COUNT query), include it in response
            response_data = {
                "results": mapped_data,
                "sql": results.get("sql", sql),
                "count": results.get("count", len(mapped_data))
            }
            
            if summary:
                response_data["summary"] = summary

            return {"answer": json.dumps(response_data, ensure_ascii=False, indent=2)}

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] NLQ Processing failed: {error_trace}")
            return {"answer": f"Server Error during processing: {str(e)}"}

    # ---------------------------------------------------------
    # Path 2: Structured/Legacy Search (Existing Logic)
    # ---------------------------------------------------------
    session = SessionLocal()
    try:
        # import json  <-- REMOVED: Caused UnboundLocalError because it shadowed the global import
        query_obj = session.query(Entity)
        
        # Handle JSON query object if present
        if is_json_query:
            try:
                parsed_query = json.loads(request.query)
                if isinstance(parsed_query, dict):
                    if "case_number" in parsed_query: request.case_number = parsed_query["case_number"]
                    if "court_name" in parsed_query: request.court_name = parsed_query["court_name"]
                    if "plaintiff" in parsed_query: request.plaintiff = parsed_query["plaintiff"]
                    if "defendant" in parsed_query: request.defendant = parsed_query["defendant"]
                    if "judge" in parsed_query: request.judge = parsed_query["judge"]
                    if "verdict" in parsed_query: request.verdict = parsed_query["verdict"]
                    request.query = None 
            except:
                pass 
        
        is_complex = False
        if request.case_number:
            query_obj = query_obj.filter(Entity.case_number.ilike(f"%{request.case_number}%"))
            is_complex = True
            
        if request.court_name:
            query_obj = query_obj.filter(Entity.court_name.ilike(f"%{request.court_name}%"))
            is_complex = True

        def json_search(column, value):
            plain = f"%{value}%"
            escaped_val = json.dumps(value).strip('"').replace('\\', '\\\\')
            escaped = f"%{escaped_val}%"
            
            return or_(
                cast(column, String).ilike(plain),
                cast(column, String).ilike(escaped)
            )

        if request.plaintiff:
            query_obj = query_obj.filter(json_search(Entity.plaintiff, request.plaintiff))
            is_complex = True
            
        if request.defendant:
            query_obj = query_obj.filter(json_search(Entity.defendant, request.defendant))
            is_complex = True
            
        if request.judge:
            query_obj = query_obj.filter(json_search(Entity.judge, request.judge))
            is_complex = True
            
        if request.verdict:
            query_obj = query_obj.filter(Entity.verdict.ilike(f"%{request.verdict}%"))
            is_complex = True
            
        if not is_complex:
            # Fallback for empty query in strict mode
            return {"answer": "Please provide a search query."}

        results = query_obj.all()
        
        if not results:
            return {"answer": "No records found matching request."}

        formatted_results = []
        for ent in results:
            rels = session.query(EntityRelationship).filter(EntityRelationship.document_id == ent.document_id).all()
            relationships_list = [
                f"{r.from_entity} -> {r.relationship_type} -> {r.to_entity}" 
                for r in rels
            ]
            
            formatted_results.append({
                "source_document": ent.document_id,
                "case_number": ent.case_number,
                "court_name": ent.court_name,
                "plaintiff": ent.plaintiff,
                "defendant": ent.defendant,
                "judge": ent.judge,
                "verdict": ent.verdict,
                "relationships": relationships_list 
            })

        return {"answer": json.dumps(formatted_results, ensure_ascii=False, indent=2)}

    except Exception as e:
        return {"error": f"Database search error: {str(e)}"}
    finally:
        session.close()


@app.get("/api/all-data")
def get_all_data(limit: int = 50):
    session = SessionLocal()
    try:
        # Fetch latest entities (Assuming 'id' is the primary key)
        entities = session.query(Entity).order_by(Entity.id.desc()).limit(limit).all()
        
        results = []
        for ent in entities:
            # Create a clean dictionary from the entity object
            item = {
                "source_document": ent.document_id,
                "case_number": ent.case_number,
                "court_name": ent.court_name,
                "judgment_date": ent.judgment_date, # Assuming this field exists and is populated
                "plaintiff": ent.plaintiff,
                "defendant": ent.defendant,
                "judge": ent.judge,
                "verdict": ent.verdict,
                "decision": ent.decision if hasattr(ent, 'decision') else None
            }

            # Parse JSON strings for list fields
            for key in ["plaintiff", "defendant", "judge"]:
                val = item.get(key)
                if val and isinstance(val, str) and val.strip().startswith("["):
                    try:
                        parsed = json.loads(val)
                        if parsed: item[key] = parsed
                    except:
                        pass
            
            # Add relationship placeholder
            item["relationships"] = []

            results.append(item)
            
        return {"results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        session.close()
