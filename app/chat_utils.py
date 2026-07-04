import os
import sys
import json
import time
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from sqlalchemy import text
from app.database import engine
from app.ollama_fallback import call_ollama, should_fallback_openrouter

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

    schema_info = """
أنت خبير PostgreSQL. الجداول المتاحة:

1. جدول [entities]: يحتوي على جميع الأعمدة التالية:
   (case_number, court_name, judge, plaintiff, defendant, plaintiff_lawyer, defendant_lawyer, verdict, reasoning)
   - يستخدم للبحث عن: أسماء القضاة، المدعين، المدعى عليهم، المحامين، أرقام القضايا، وعدد القضايا.
   - **هام جداً**: استخدم `plaintiff_lawyer` للبحث عن محامي المدعي، واستخدم `defendant_lawyer` للبحث عن محامي المدعى عليه. ليس لدينا عامود باسم (lawyer_name).
   - **انتبه جداً**: أعمدة الأطراف مثل (judge, plaintiff, defendant, plaintiff_lawyer, defendant_lawyer) مبرمجة كـ JSON. يجب عليك تحويلها إلى نص عند البحث باستخدام ::text.

2. جدول [entity_relationships]: يحتوي على (from_entity, relationship_type, to_entity).
   - يستخدم **فقط** عند السؤال عن كلمة "علاقات" أو "روابط".

أمثلة (التزم بنفس النمط تماماً):
س: كم عدد قضايا القاضي أحمد المغني؟
ج: SELECT COUNT(*) FROM entities WHERE judge::text LIKE '%أحمد المغني%';

س: اعطيني محامي المدعي في القضية التي رقمها 2016/848
ج: SELECT plaintiff_lawyer FROM entities WHERE case_number = '2016/848';

س: ابحث عن علاقات أحمد
ج: SELECT * FROM entity_relationships WHERE from_entity LIKE '%أحمد%' OR to_entity LIKE '%أحمد%';

س: تفاصيل قضايا المتهم علي
ج: SELECT * FROM entities WHERE defendant::text LIKE '%علي%';

قواعد حاسمة:
- قاعدة البيانات هي PostgreSQL.
- ممنوع استخدام JOIN نهائياً في نفس الجدول.
- لا تخترع أسماء أعمدة غير موجودة في القائمة أعلاه (لا تستخدم lawyer_name نهائياً).
- للبحث داخل قوائم الـ JSON، استخدم دائماً `column_name::text LIKE '%value%'`.
- أرجع فقط كود SQL.
"""

    system_prompt = f"أنت خبير SQL متخصص في القضايا القانونية العربية. مهمتك هي تحويل السؤال إلى SQL بدقة متناهية.\n{schema_info}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"حول هذا السؤال إلى SQL: {user_question}"}
    ]

    import re

    def _extract_sql(raw: str) -> str:
        """Strip markdown fences and extract the SELECT statement."""
        if "```sql" in raw:
            raw = raw.split("```sql")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        match = re.search(r'(SELECT\s+.*)', raw, re.IGNORECASE | re.DOTALL)
        if match:
            raw = match.group(1).strip()
        return raw.rstrip(';').strip()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Calling OpenRouter ({MODEL_NAME}) (attempt {attempt + 1})...")
            response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
            sql = response.choices[0].message.content.strip()
            return _extract_sql(sql)

        except Exception as e:
            print(f"[TEXT-SQL] OpenRouter error (attempt {attempt + 1}): {e}")

            if should_fallback_openrouter(e):
                try:
                    print("[TEXT-SQL] Falling back to local qwen3 via Ollama...")
                    raw = call_ollama(messages)
                    return _extract_sql(raw)
                except Exception as fallback_err:
                    print(f"[TEXT-SQL] Ollama fallback failed: {fallback_err}")
                    return None

            if attempt < max_retries - 1:
                time.sleep(1)
            continue

    return None


def execute_sql(sql, user_question=""):
    """
    Execute SQL query using SQLAlchemy engine.
    If COUNT query detected, also fetch full details.
    """
    if not sql or not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries allowed or invalid SQL generated"}
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            rows = result.fetchall()
            
            # Map Row objects to dictionaries
            results = [dict(row._mapping) for row in rows]
            
            # Detect if this is a COUNT(*) query
            is_count_query = "count(*)" in sql.lower()
            
            if is_count_query and results:
                # Extract the count value from the first result
                count_value = list(results[0].values())[0] if results[0] else 0
                
                # Generate a new query to fetch details by replacing COUNT(*) with *
                import re
                details_sql = re.sub(r'count\(\s*\*\s*\)', '*', sql, flags=re.IGNORECASE)
                
                # Execute the details query
                details_result = connection.execute(text(details_sql))
                details_rows = details_result.fetchall()
                details = [dict(row._mapping) for row in details_rows]
                
                return {
                    "success": True, 
                    "count": count_value,
                    "summary": f"تم العثور على {count_value} من القضايا ",
                    "data": details,
                    "sql": details_sql
                }
            
            return {"success": True, "count": len(results), "data": results, "sql": sql}
            
    except Exception as e:
        return {"error": str(e)}
