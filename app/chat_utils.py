import os
import sys
import json
import time
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from sqlalchemy import text
from app.database import engine

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

def get_sql_from_llm(user_question):
    """
    Convert natural language question to SQL using OpenRouter LLM.
    """
    if not client:
        print("[ERROR] OpenRouter API key not configured")
        return None

    # Detect if we are using PostgreSQL or SQLite to adjust the prompt
    is_postgres = engine.url.drivername.startswith("postgresql")
    like_op = "ILIKE" if is_postgres else "LIKE"

    schema_info = f"""
أنت خبير قاعدة بيانات {"PostgreSQL" if is_postgres else "SQLite"}. الجداول المتاحة:

1. جدول [entities]: يحتوي على (case_number, court_name, judge, plaintiff, defendant, verdict, reasoning).
   - يستخدم للبحث عن: أسماء القضاة، المدعين، المدعى عليهم، أرقام القضايا، وعدد القضايا.

2. جدول [entity_relationships]: يحتوي على (from_entity, relationship_type, to_entity).
   - يستخدم **فقط** عند السؤال عن كلمة "علاقات" أو "روابط".

قواعد حاسمة:
- استخدم العمليات الحسابية القياسية.
- للبحث النصي، استخدم المشغل **{like_op}** لضمان عدم الحساسية لحالة الأحرف.
- ممنوع استخدام JOIN نهائياً.
- ممنوع وضع % داخل الاسم (مثلاً '%أحمد %علي%' خطأ، الصحيح '%أحمد علي%').
- أرجع فقط كود SQL.

أمثلة:
س: كم عدد قضايا القاضي أحمد المغني؟
ج: SELECT COUNT(*) FROM entities WHERE judge {like_op} '%أحمد المغني%';
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
            
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            import re
            match = re.search(r'(SELECT\s+.*)', sql, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1).strip()
            
            sql = sql.rstrip(';').strip()
            return sql
        except Exception as e:
            print(f"Error: {e}")
            if attempt < max_retries - 1: time.sleep(1)
            continue
    return None


def execute_sql(sql, user_question=""):
    """
    Execute SQL query using SQLAlchemy engine.
    """
    if not sql or not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries allowed or invalid SQL generated"}
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            rows = result.fetchall()
            
            # Map Row objects to dictionaries
            results = [dict(row._mapping) for row in rows]
            
            return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        return {"error": str(e)}
