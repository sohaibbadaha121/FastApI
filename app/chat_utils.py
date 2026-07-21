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

api_key = os.getenv("GROQ_API_KEY")

client = None
if api_key:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_sql_from_llm(user_question):
    """
    Convert natural language question to SQL using Groq LLM.
    Falls back to local Ollama on ANY API failure.
    """
    print("\n" + "═"*70, flush=True)
    print(f"[TEXT-SQL] INPUT QUESTION: {user_question}", flush=True)
    print("═"*70 + "\n", flush=True)

    if not client:
        print("[ERROR] Groq API key not configured", flush=True)
        return None

    # -----------------------------------------------------------------------
    # SCHEMA PROMPT — matches the REAL PostgreSQL (Neon) database exactly
    # -----------------------------------------------------------------------
    schema_info = """
أنت خبير SQL متخصص بقاعدة بيانات قضائية فلسطينية (PostgreSQL).

═══════════════════════════════════════════════════
 الجدول الرئيسي: entities
═══════════════════════════════════════════════════
الأعمدة وأنواعها:
  • case_number      VARCHAR   — رقم القضية مثل '563/2021' أو '476/2021'
  • court_name       VARCHAR   — اسم المحكمة (مثال: 'محكمة النقض', 'محكمة العدل العليا')
  • judgment_date    VARCHAR   — تاريخ الحكم بصيغة نصية، قد تحتوي على مسافات، بصيغتين: d/m/yyyy مثل '6/9/2021' أو yyyy/mm/dd مثل '2018/01/21'
  • case_type        VARCHAR   — نوع القضية: 'مدني' أو 'جزائي'
  • verdict          TEXT      — نص الحكم مثل 'رد الطعن/الدعوى'
  • reasoning        TEXT      — أسباب الحكم
  • decision         TEXT      — قرار المحكمة
  • chief_judge      VARCHAR   — رئيس الهيئة القضائية

  — أعمدة JSON (تحتوي على قوائم نصوص):
  • judge            JSON      — قائمة بأسماء القضاة
  • plaintiff        JSON      — قائمة بأسماء المدعين
  • defendant        JSON      — قائمة بأسماء المدعى عليهم
  • plaintiff_lawyer JSON      — قائمة بأسماء محامي المدعي
  • defendant_lawyer JSON      — قائمة بأسماء محامي المدعى عليه
  • legal_articles   JSON      — قائمة بالمواد القانونية المستشهد بها
  • court_members    JSON      — أعضاء الهيئة القضائية

═══════════════════════════════════════════════════
 جدول ثانوي: entity_relationships
═══════════════════════════════════════════════════
  • from_entity, relationship_type, to_entity
  — استخدمه فقط عند السؤال عن "علاقات" أو "روابط"

═══════════════════════════════════════════════════
 قواعد حاسمة وإجبارية
═══════════════════════════════════════════════════

1. البحث داخل أعمدة JSON — استخدم column_name::text LIKE:
       judge::text LIKE '%محمد%'
       plaintiff::text LIKE '%شركة ترست%'

2. لعدّ عناصر مصفوفة JSON (عدد القضاة، عدد الأطراف):
       jsonb_array_length(judge::jsonb)
   مثال: SELECT jsonb_array_length(judge::jsonb) FROM entities WHERE case_number = '476/2021'

3. لاستخراج عناصر مصفوفة JSON كقوائم:
       SELECT jsonb_array_elements_text(legal_articles::jsonb) FROM entities WHERE case_number = '476/2021'

4. البحث بالتاريخ — التواريخ نصية، قد تحتوي مسافات:
       replace(judgment_date, ' ', '') = '15/9/2021'
       replace(judgment_date, ' ', '') = '1/9/2021'

5. ترتيب التواريخ (ORDER BY) — لا تستخدم الترتيب النصي، استخدم CASE:
       ORDER BY CASE
         WHEN replace(judgment_date, ' ', '') ~ '^\\d{4}' THEN to_date(replace(judgment_date, ' ', ''), 'YYYY/MM/DD')
         ELSE to_date(replace(judgment_date, ' ', ''), 'DD/MM/YYYY')
       END ASC

6. لا تستخدم جداول غير موجودة: cases, plaintiffs, defendants, judges, lawyers
7. لا تستخدم JOIN على نفس الجدول
8. أرجع SQL فقط بدون أي شرح

═══════════════════════════════════════════════════
 أمثلة صحيحة ومُختبَرة على قاعدة البيانات الحقيقية
═══════════════════════════════════════════════════

س: كم عدد القضايا؟
ج: SELECT COUNT(*) FROM entities;

س: من هو محامي المدعى عليه في القضية رقم 588/2021؟
ج: SELECT defendant_lawyer FROM entities WHERE case_number = '588/2021';

س: من هو محامي المدعي في القضية رقم 76/2021؟
ج: SELECT plaintiff_lawyer FROM entities WHERE case_number = '76/2021';

س: ما هو تاريخ الحكم في القضية رقم 563/2021؟
ج: SELECT judgment_date FROM entities WHERE case_number = '563/2021';

س: كم عدد القضاة في القضية رقم 476/2021؟
ج: SELECT jsonb_array_length(judge::jsonb) FROM entities WHERE case_number = '476/2021';

س: كم عدد المدعى عليهم في القضية رقم 552/2021؟
ج: SELECT jsonb_array_length(defendant::jsonb) FROM entities WHERE case_number = '552/2021';

س: كم عدد القضايا بتاريخ 1/9/2021؟
ج: SELECT COUNT(*) FROM entities WHERE replace(judgment_date, ' ', '') = '1/9/2021';

س: ما هي المواد القانونية في القضية رقم 476/2021؟
ج: SELECT jsonb_array_elements_text(legal_articles::jsonb) FROM entities WHERE case_number = '476/2021';

س: كم عدد المواد القانونية في القضية رقم 72/2021؟
ج: SELECT jsonb_array_length(legal_articles::jsonb) FROM entities WHERE case_number = '72/2021';

س: كم عدد المحاكم المختلفة؟
ج: SELECT COUNT(DISTINCT court_name) FROM entities;

س: ما هو رقم القضية الجزائية؟
ج: SELECT case_number FROM entities WHERE case_type = 'جزائي';

س: ما هي القضايا بتاريخ 15/9/2021؟
ج: SELECT case_number FROM entities WHERE replace(judgment_date, ' ', '') = '15/9/2021';

س: من هو المدعي في القضية 563/2021 وكم عدد قضاتها؟
ج: SELECT plaintiff, jsonb_array_length(judge::jsonb) AS judges_count FROM entities WHERE case_number = '563/2021';

س: ما هي القضايا التي استندت للمادة 152؟
ج: SELECT case_number FROM entities WHERE legal_articles::text LIKE '%152%';

س: ما هي القضايا التي محامي المدعى عليه فيها محمد جرار؟
ج: SELECT case_number FROM entities WHERE defendant_lawyer::text LIKE '%محمد جرار%';

س: كم عدد القضايا التي ترست العالمية مدعية فيها؟
ج: SELECT COUNT(*) FROM entities WHERE plaintiff::text LIKE '%ترست%';

س: كم عدد قضايا القاضي أحمد المغني؟
ج: SELECT COUNT(*) FROM entities WHERE judge::text LIKE '%أحمد المغني%';

س: ما هو الحكم في القضية 413/2019؟
ج: SELECT verdict FROM entities WHERE case_number = '413/2019';

س: ما هي أبكر قضية من حيث التاريخ؟
ج: SELECT case_number, judgment_date FROM entities WHERE judgment_date IS NOT NULL AND judgment_date != '' AND judgment_date LIKE '%/%' ORDER BY CASE WHEN replace(judgment_date, ' ', '') ~ '^\\d{4}' THEN to_date(replace(judgment_date, ' ', ''), 'YYYY/MM/DD') ELSE to_date(replace(judgment_date, ' ', ''), 'DD/MM/YYYY') END ASC LIMIT 1;

س: ابحث عن علاقات أحمد
ج: SELECT * FROM entity_relationships WHERE from_entity LIKE '%أحمد%' OR to_entity LIKE '%أحمد%';
"""

    system_prompt = (
        "أنت خبير SQL متخصص في القضايا القانونية العربية. "
        "مهمتك هي تحويل السؤال إلى SQL بدقة متناهية.\n" + schema_info
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"حول هذا السؤال إلى SQL: {user_question}"}
    ]

    import re

    def _extract_sql(raw: str) -> str:
        """Strip markdown fences and extract the SQL statement.

        Handles:
          - Bare SELECT ...
          - WITH cte AS (SELECT ...)  — Common Table Expressions
          - EXPLAIN [ANALYZE] SELECT ... — query-plan prefixes
        Returns the cleaned SQL string, or the stripped raw text if no
        recognised keyword is found (so callers still receive something
        to validate rather than a silent None).
        """
        # 1. Strip markdown code fences
        if "```sql" in raw:
            raw = raw.split("```sql")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        # 2. Match any of the recognised SQL entry-points:
        match = re.search(
            r'((?:WITH|EXPLAIN)\s+.*|SELECT\s+.*)',
            raw,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            raw = match.group(1).strip()

        return raw.rstrip(';').strip()

    max_retries = 3
    final_sql = None
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Calling Groq ({MODEL_NAME}) (attempt {attempt + 1})...", flush=True)
            response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
            sql = response.choices[0].message.content.strip()
            final_sql = _extract_sql(sql)
            break

        except Exception as e:
            print(f"[TEXT-SQL] Groq error (attempt {attempt + 1}): {e}", flush=True)

            # Always fallback on rate-limit errors OR on the final retry
            if should_fallback_openrouter(e) or attempt == max_retries - 1:
                try:
                    print("[TEXT-SQL] Falling back to local qwen3 via Ollama...", flush=True)
                    raw = call_ollama(messages)
                    final_sql = _extract_sql(raw)
                    break
                except Exception as fallback_err:
                    print(f"[TEXT-SQL] Ollama fallback failed: {fallback_err}", flush=True)
                    final_sql = None
                    break

            if attempt < max_retries - 1:
                time.sleep(1)
            continue

    print("\n" + "═"*70, flush=True)
    print(f"[TEXT-SQL] FINAL SQL RETURNED: {final_sql}", flush=True)
    print("═"*70 + "\n", flush=True)
    return final_sql


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

                import re

                # -------------------------------------------------------
                # Edge-case guard: GROUP BY / HAVING / UNION queries
                # -------------------------------------------------------
                sql_upper = sql.upper()
                has_group_by = re.search(r'\bGROUP\s+BY\b', sql_upper) is not None
                has_having   = re.search(r'\bHAVING\b',     sql_upper) is not None
                has_union    = re.search(r'\bUNION\b',       sql_upper) is not None

                if has_group_by or has_having or has_union:
                    # Return only the aggregate count — no re-query
                    return {
                        "success": True,
                        "count": count_value,
                        "summary": f"تم العثور على {count_value} من القضايا",
                        "data": results,
                        "sql": sql,
                    }

                # Safe to replace COUNT(*) with * and fetch full rows
                details_sql = re.sub(r'count\(\s*\*\s*\)', '*', sql, flags=re.IGNORECASE)

                # Execute the details query
                details_result = connection.execute(text(details_sql))
                details_rows = details_result.fetchall()
                details = [dict(row._mapping) for row in details_rows]

                return {
                    "success": True,
                    "count": count_value,
                    "summary": f"تم العثور على {count_value} من القضايا",
                    "data": details,
                    "sql": details_sql,
                }

            return {"success": True, "count": len(results), "data": results, "sql": sql}

    except Exception as e:
        return {"error": str(e)}