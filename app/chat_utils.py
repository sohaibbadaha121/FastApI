import os
import sys
import json
import sqlite3
import time
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

env_file = find_dotenv()
if env_file:
    load_dotenv(env_file, override=True)

api_key = (
    os.getenv("OPENROUTER_API_KEY") or 
    os.getenv("OPENROUTER_KEY") or 
    os.getenv("OPENROUTER") or
    os.getenv("OPEN_ROUTER") or
    os.getenv("OPEN_ROUTER_API_KEY")
)

client = None
if api_key:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

MODEL_NAME = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
DB_PATH = "legal_documents.db"

def get_sql_from_llm(user_question):
    """
    Convert natural language question to SQL using OpenRouter LLM.
    """
    if not client:
        print("[ERROR] OpenRouter API key not configured")
        return None

    schema_info = """
أنت خبير SQLite. الجداول المتاحة:

1. جدول [entities]: يحتوي على (case_number, court_name, judge, plaintiff, defendant, verdict, reasoning).
   - يستخدم للبحث عن: أسماء القضاة، المدعين، المدعى عليهم، أرقام القضايا، وعدد القضايا.

2. جدول [entity_relationships]: يحتوي على (from_entity, relationship_type, to_entity).
   - يستخدم **فقط** عند السؤال عن كلمة "علاقات" أو "روابط".

أمثلة (التزم بنفس النمط تماماً):
س: كم عدد قضايا القاضي أحمد المغني؟
ج: SELECT COUNT(*) FROM entities WHERE judge LIKE '%أحمد المغني%';

س: ابحث عن علاقات أحمد
ج: SELECT * FROM entity_relationships WHERE from_entity LIKE '%أحمد%' OR to_entity LIKE '%أحمد%';

س: تفاصيل قضايا المتهم علي
ج: SELECT * FROM entities WHERE defendant LIKE '%علي%';

قواعد حاسمة:
- ممنوع استخدام JOIN نهائياً.
- ممنوع وضع % داخل الاسم (مثلاً '%أحمد %علي%' خطأ، الصحيح '%أحمد علي%').
- أرجع فقط كود SQL.
"""

    system_prompt = f"أنت خبير SQL متخصص في القضايا القانونية العربية. مهمتك هي تحويل السؤال إلى SQL بدقة متناهية.\n{schema_info}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"حول هذا السؤال إلى SQL: {user_question}"}
    ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Calling OpenRouter ({MODEL_NAME}) (attempt {attempt + 1})...")
            response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
            
            sql = response.choices[0].message.content.strip()
            print(f"[DEBUG] Raw Response: {sql}")
            
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            import re
            match = re.search(r'(SELECT\s+.*)', sql, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1).strip()
            
            sql = sql.rstrip(';').strip()
            
            print(f"[DEBUG] Final SQL: {sql}")
            return sql
        except Exception as e:
            print(f"Error: {e}")
            if attempt < max_retries - 1: time.sleep(1)
            continue
    return None


def execute_sql(sql, user_question=""):
    """
    Execute SQL query on the database.
    """
    if not sql or not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries allowed or invalid SQL generated"}
    
    try:
        db_path_absolute = os.path.abspath(DB_PATH)
        conn = sqlite3.connect(db_path_absolute)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        results = [dict(row) for row in rows]
        
        conn.close()
        
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        return {"error": str(e)}
