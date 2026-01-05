import os
import sys
import json
import sqlite3
import time
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

# Load environment
env_file = find_dotenv()
if env_file:
    load_dotenv(env_file, override=True)

# Try different common variable names for OpenRouter
api_key = (
    os.getenv("OPENROUTER_API_KEY") or 
    os.getenv("OPENROUTER_KEY") or 
    os.getenv("OPENROUTER") or
    os.getenv("OPEN_ROUTER") or
    os.getenv("OPEN_ROUTER_API_KEY")
)

if not api_key:
    # Fallback search
    for key, value in os.environ.items():
        if "OPENROUTER" in key.upper() and "KEY" in key.upper():
            api_key = value
            break

if not api_key:
    print("ERROR: OpenRouter API Key not found. Please set OPENROUTER_API_KEY in your .env file")
    sys.exit(1)

# Configure OpenAI client for OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)

# Use a free model by default, or one from env
MODEL_NAME = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
DB_PATH = "legal_documents.db"

def get_sql_from_llm(user_question):
    """
    Convert natural language question to SQL using OpenRouter LLM.
    """
    schema_info = """
Database Schema:

Table: entities
- id (INTEGER)
- document_id (INTEGER)
- case_number (TEXT)
- court_name (TEXT)
- judgment_date (TEXT)
- plaintiff (JSON array - stored as TEXT with Unicode escapes)
- defendant (JSON array - stored as TEXT with Unicode escapes)
- judge (JSON array - stored as TEXT with Unicode escapes)
- plaintiff_lawyer (JSON array - stored as TEXT with Unicode escapes)
- defendant_lawyer (JSON array - stored as TEXT with Unicode escapes)
- decision (TEXT)
- verdict (TEXT)

Table: documents
- id (INTEGER)
- filename (TEXT)
- status (TEXT)

IMPORTANT RULES:
1. Return ONLY the SQL query, no explanation, no markdown.
2. Use only SELECT statements.
3. **Searching Names (Judge, Lawyer, etc)**:
   - The columns are stored as JSON arrays (e.g. `["Ahmed", "Ali"]`).
   - To search, ALWAYS use `LIKE` with wildcards.
   - Example: `WHERE judge LIKE '%Ahmed%'`
4. **Select vs Count (CRITICAL)**:
   - If the user asks for "details", "case number", "who", "what", "give me", "find"... YOU MUST USE `SELECT *` (or `SELECT column_name`).
   - ONLY use `SELECT COUNT(*)` if the user explicitly asks "how many" (كم عدد) or "count" (احسب).
   - NEVER use `COUNT` if the user wants to see the actual data.

Examples:
- "Find judge ايمن زهران"                     -> SELECT * FROM entities WHERE judge LIKE '%ايمن زهران%'
- "اعطيني رقم القضية التي فيها القاضي ايمن"   -> SELECT case_number FROM entities WHERE judge LIKE '%ايمن%'
- "Show me cases with lawyer Ahmad"           -> SELECT * FROM entities WHERE plaintiff_lawyer LIKE '%Ahmad%' OR defendant_lawyer LIKE '%Ahmad%'
- "كم عدد القضايا؟"                           -> SELECT COUNT(*) as total FROM entities
- "How many cases for judge Ali?"             -> SELECT COUNT(*) as total FROM entities WHERE judge LIKE '%Ali%'
"""

    system_prompt = f"""You are a SQL expert helper.
{schema_info}
Return ONLY the raw SQL query. Do not use markdown blocks (`sql).
Rule of thumb: If you are not sure, use `SELECT *` instead of `COUNT`."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate SQL query for: {user_question}"}
    ]

    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Calling OpenRouter ({MODEL_NAME}) (attempt {attempt + 1}/{max_retries})...")
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )
            
            print(f"[DEBUG] Got response from OpenRouter")
            sql = response.choices[0].message.content.strip()
            print(f"[DEBUG] Raw SQL: {sql}")
            
            # Clean markdown if present
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            # Remove any trailing semicolons or extra whitespace
            sql = sql.rstrip(';').strip()
            
            print(f"[DEBUG] Cleaned SQL: {sql}")
            return sql
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR calling LLM (attempt {attempt + 1}): {type(e).__name__}")
            print(f"ERROR details: {error_msg}")
            
            # Check if it's a rate limit error (usually 429)
            if "429" in error_msg or "rate" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
            
            # For other errors, don't retry immediately unless network glitch
            if attempt < max_retries - 1:
                 time.sleep(retry_delay)
                 continue
            
            return None
    
    print("All retries exhausted")
    return None

def execute_sql(sql, user_question=""):
    """
    Execute SQL query on the database.
    """
    if not sql or not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries allowed or invalid SQL generated"}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        results = [dict(row) for row in rows]
        
        conn.close()
        
        # Apply Python filtering ONLY if necessary
        # If the SQL contains "WHERE", it means the DB already filtered the results for us.
        # We only need Python filtering if we did a blind "SELECT * FROM entities" without conditions.
        has_where = "where" in sql.lower()
        if user_question and results and not has_where:
             results = filter_results_by_names(results, user_question)
        
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        return {"error": str(e)}

def filter_results_by_names(results, user_question):
    """
    Filter results based on names mentioned in the question.
    Searches in JSON fields (judge, plaintiff, defendant, lawyers).
    """
    # Extract potential names from question (simple approach)
    # Look for Arabic names or specific keywords
    keywords = {
        'قاضي': 'judge',
        'القاضي': 'judge',
        'judge': 'judge',
        'مدعي': 'plaintiff',
        'المدعي': 'plaintiff',
        'plaintiff': 'plaintiff',
        'مدعى': 'defendant',
        'المدعى': 'defendant',
        'defendant': 'defendant',
        'محامي': 'lawyer',
        'المحامي': 'lawyer',
        'lawyer': 'lawyer'
    }
    
    # Detect which field to search
    field_to_search = None
    for keyword, field in keywords.items():
        if keyword in user_question.lower():
            field_to_search = field
            break
    
    # If no specific field keyword found, don't filter
    if not field_to_search:
        return results
    
    # Validating stop words with more robust approach
    stop_words = ['اعطيني', 'جميع', 'القضايا', 'الي', 'طبيعة', 'كان', 'فيها', 'هو', 'التي', 'عدد', 'كم', 'كمية', 'عن', 'رقم', 'القضية', 'find', 'all', 'cases', 'with', 'where', 'the', 'is', 'was', 'how', 'many', 'count']
    
    words = user_question.split()
    # Normalize words and filter
    name_parts = []
    for w in words:
        clean_w = w.strip()
        if len(clean_w) > 1 and clean_w not in stop_words and clean_w not in keywords.keys():
            name_parts.append(clean_w)
    
    if not name_parts:
        return results
    
    # Remove 'عدد' explicitly if it snuck in (redundant safety)
    if 'عدد' in name_parts: name_parts.remove('عدد')
    
    print(f"[DEBUG] Filtering by {field_to_search} containing: {name_parts}")
    
    print(f"[DEBUG] Filtering by {field_to_search} containing: {name_parts}")
    
    # Filter results
    filtered = []
    for row in results:
        if field_to_search == 'lawyer':
            # Search both plaintiff and defendant lawyers
            fields_to_check = [row.get('plaintiff_lawyer'), row.get('defendant_lawyer')]
        else:
            fields_to_check = [row.get(field_to_search)]
        
        for field_value in fields_to_check:
            if field_value:
                match = matches_name(field_value, name_parts)
                if match:
                    print(f"[DEBUG] MATCH! Case: {row.get('case_number')}")
                    filtered.append(row)
                    break
    
    print(f"[DEBUG] Filtered {len(filtered)} out of {len(results)} results")
    return filtered

def matches_name(json_field, name_parts):
    """
    Check if JSON field contains name parts (with Arabic normalization).
    """
    def normalize_arabic(text):
        if not text: return ""
        text = str(text).lower()
        # Normalize Alefs
        text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        # Normalize Taa Marbuta
        text = text.replace('ة', 'ه')
        # Remove 'Al-' prefix (ال) from words
        words = text.split()
        norm_words = []
        for w in words:
            if w.startswith('ال') and len(w) > 3: # Only remove if word is long enough
                norm_words.append(w[2:])
            else:
                norm_words.append(w)
        return " ".join(norm_words)

    try:
        # Parse JSON
        names = json.loads(json_field)
        if not isinstance(names, list):
            names = [names]
        
        # Normalize search parts
        norm_parts = [normalize_arabic(p) for p in name_parts]
        
        # Check if any name matches
        for name in names:
            norm_name = normalize_arabic(name)
            
            # Check if ALL parts are present in the name
            # strict=False means partial word matches allowed? 
            # Let's try exact word matching first, or simple substring
            
            # Simple substring matching on normalized strings
            # If user said "Al-Zahran", norm is "Zahran".
            # DB has "Zahran", norm is "Zahran". -> Match!
            
            match_count = 0
            for part in norm_parts:
                if part in norm_name:
                    match_count += 1
            
            if match_count == len(norm_parts):
                return True
                
        return False
    except Exception as e:
        print(f"[DEBUG] Error in matches_name: {e}")
        return False


def format_results(user_question, sql, results):
    """
    Format results in a readable way using LLM.
    """
    if "error" in results:
        return f"Error: {results['error']}"
    
    if results['count'] == 0:
        return "No results found."
    
    # Show first 3 results
    sample_data = json.dumps(results['data'][:3], ensure_ascii=False, indent=2)
    
    system_prompt = "You are a helpful legal assistant. Summarize the database results in Arabic for the user."
    user_prompt = f"""
User asked: {user_question}
SQL query: {sql}
Found {results['count']} results.

Sample data (first 3):
{sample_data}

Provide a helpful answer in Arabic summarizing the results. Include key details like case numbers, names, dates.
"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Found {results['count']} results but couldn't format: {e}"

def main():
    print("=" * 60)
    print("Legal Database Chat (OpenRouter/OpenAI Version)")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    
    # Check if question provided as argument
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"\nQuestion: {question}")
        
        # Step 1: Generate SQL
        print("\nGenerating SQL...")
        sql = get_sql_from_llm(question)
        if not sql:
            print("Failed to generate SQL")
            return
        
        print(f"SQL: {sql}")
        
        # Step 2: Execute SQL
        print("\nExecuting query...")
        results = execute_sql(sql, question)
        
        # Step 3: Direct Output (No Formatting)
        # print("\nFormatting results...") # Skipped
        # answer = format_results(question, sql, results)
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        if "error" in results:
            print(f"Error: {results['error']}")
        else:
            print(f"Count: {results.get('count', 0)}")
            print(json.dumps(results.get('data', []), ensure_ascii=False, indent=2))
        print("=" * 60)
        return
    
    # Interactive mode
    print("\nType your question (or 'exit' to quit)")
    print("Examples:")
    print("  - How many cases are there?")
    print("  - اعطيني القضايا التي فيها القاضي ايمن زهران")
    print("  - Find all cases in محكمة النقض")
    print()
    
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not question or question.lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
        
        print("\n[Generating SQL...]")
        sql = get_sql_from_llm(question)
        if not sql:
            print("Failed to generate SQL\n")
            continue
        
        print(f"[SQL: {sql}]")
        
        print("[Executing...]")
        results = execute_sql(sql, question)
        
        print("[Results:]")
        if "error" in results:
            print(f"Error: {results['error']}")
        else:
            print(f"Count: {results.get('count', 0)}")
            print(json.dumps(results.get('data', []), ensure_ascii=False, indent=2))
            
        print("-" * 60)

if __name__ == "__main__":
    main()
