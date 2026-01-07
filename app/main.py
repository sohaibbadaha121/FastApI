
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
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
OR_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
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
async def ask_question(file: UploadFile = File(...), question: str = Form(...)):
    """
    Revised endpoint to handle PDF upload and question answering.
    Replaces the previous text-based ask endpoint.
    """
    temp_path = f"temp_{file.filename}"
    
    try:
        # 1. Save the uploaded file temporarily
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Extract text using our existing processor
        law_text = extract_text_from_pdf(temp_path)
        
        if not law_text:
            return {"error": "Could not extract text from the PDF file."}

        if not or_client:
            return {"error": "OpenRouter API key is not configured. Please check your .env file."}

        # 3. Use OpenRouter to answer the question
        prompt = f"""
You are a legal assistant AI.
Here is a law text extracted from a PDF:
{law_text}

The user asks this question based on the content above:
{question}

Give a clear and correct answer in Arabic based only on the text provided.
"""
        messages = [
            {"role": "user", "content": prompt}
        ]
        
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
        # 4. Clean up the temporary file
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
            

            mapped_data = []
            for row in data:
                item = dict(row)
                clean_item = {"source_document": item.get("document_id")}
                for k, v in item.items():
                    if k in ["raw_entities", "created_at", "id", "document_id"] or v in ["null", None, "", []]: continue
                    if isinstance(v, str) and v.startswith("["):
                        try:
                            parsed = json.loads(v)
                            if parsed: clean_item[k] = parsed
                            continue
                        except: pass
                    clean_item[k] = v
                if "relationships" not in clean_item: clean_item["relationships"] = []
                mapped_data.append(clean_item)
                
            return {"answer": json.dumps(mapped_data, ensure_ascii=False, indent=2)}

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
