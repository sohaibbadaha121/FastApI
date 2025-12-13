
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Document, Entity, EntityRelationship
from typing import Optional, List
from sqlalchemy import or_, cast, String

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    lawText: str
    question: str

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
async def ask_question(request: QueryRequest):
    law_text = request.lawText
    question = request.question

    prompt = f"""
You are a legal assistant AI.
Here is a law text:
{law_text}
The user asks this question:
{question}
Give a clear and correct answer based only on the law text.
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return {"answer": response.text}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/db-query")
async def query_database(request: DbQueryRequest):
    session = SessionLocal()
    try:
        import json
        query_obj = session.query(Entity)
        
        if request.query and request.query.strip().startswith("{"):
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
            if not request.query:
                return {"answer": "Please provide a search query."}
                
            user_query = request.query.strip()
            keywords = user_query.split()
            
            for keyword in keywords:
                term_raw = f"%{keyword}%"
                
                import json
                json_str = json.dumps(keyword).strip('"')  
                term_json_a = f"%{json_str}%"
                json_str_escaped = json_str.replace('\\', '\\\\')
                term_json_b = f"%{json_str_escaped}%"
                
                query_obj = query_obj.filter(
                    or_(
                    
                        Entity.case_number.ilike(term_raw),
                        Entity.court_name.ilike(term_raw),
                        Entity.verdict.ilike(term_raw),
                        
                        cast(Entity.plaintiff, String).ilike(term_raw),
                        cast(Entity.plaintiff, String).ilike(term_json_a),
                        cast(Entity.plaintiff, String).ilike(term_json_b),
                        
                        cast(Entity.defendant, String).ilike(term_raw),
                        cast(Entity.defendant, String).ilike(term_json_a),
                        cast(Entity.defendant, String).ilike(term_json_b),
                        
                        cast(Entity.judge, String).ilike(term_raw),
                        cast(Entity.judge, String).ilike(term_json_a),
                        cast(Entity.judge, String).ilike(term_json_b)
                    )
                )
            
       
        results = query_obj.all()
        
        if not results:
            msg = f"No records found matching request."
            return {"answer": msg}

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
