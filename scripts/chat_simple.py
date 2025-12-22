import os
import sys
import json
import sqlite3
import time
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    sys.exit(1)

genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"  # Use stable model
DB_PATH = "legal_documents.db"

def get_sql_from_gemini(user_question):
    """
    Convert natural language question to SQL using Gemini.
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
1. Return ONLY the SQL query, no explanation, no markdown
2. Use only SELECT statements
3. **CRITICAL**: For searching names in JSON columns (judge, plaintiff, defendant, lawyers):
   - DO NOT use WHERE clauses with LIKE
   - Just return: SELECT * FROM entities
   - Python will filter the results after
4. For non-JSON fields (court_name, case_number), you CAN use WHERE LIKE
5. For counting, use COUNT(*)

Examples:
- "Find judge ايمن زهران" → SELECT * FROM entities
- "Find plaintiff أحمد" → SELECT * FROM entities  
- "Find cases in محكمة النقض" → SELECT * FROM entities WHERE court_name LIKE '%محكمة النقض%'
- "How many cases?" → SELECT COUNT(*) as total FROM entities
"""

    prompt = f"""{schema_info}

User Question: {user_question}

Generate the SQL query:"""

    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            print(f"[DEBUG] Calling Gemini (attempt {attempt + 1}/{max_retries})...")
            response = model.generate_content(prompt)
            print(f"[DEBUG] Got response from Gemini")
            sql = response.text.strip()
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
            print(f"ERROR calling Gemini (attempt {attempt + 1}): {type(e).__name__}")
            print(f"ERROR details: {error_msg}")
            
            # Check if it's a rate limit error
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
            
            # For other errors, don't retry
            import traceback
            traceback.print_exc()
            return None
    
    print("All retries exhausted")
    return None

def execute_sql(sql, user_question=""):
    """
    Execute SQL query on the database.
    """
    if not sql or not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries allowed"}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        results = [dict(row) for row in rows]
        
        conn.close()
        
        # Apply Python filtering if needed
        if user_question and results:
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
    
    # Extract name parts (words that might be names)
    # Remove common question words but keep potential names
    stop_words = ['اعطيني', 'جميع', 'القضايا', 'الي', 'كان', 'فيها', 'هو', 'التي', 'find', 'all', 'cases', 'with', 'where', 'the', 'is', 'was']
    words = user_question.split()
    name_parts = [w for w in words if w not in stop_words and w not in keywords.keys() and len(w) > 1]
    
    if not name_parts:
        return results
    
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
    Check if JSON field contains all name parts.
    """
    try:
        # Parse JSON
        names = json.loads(json_field)
        if not isinstance(names, list):
            names = [names]
        
        # Check if any name contains all parts
        for name in names:
            name_lower = str(name).lower()
            all_match = all(part.lower() in name_lower for part in name_parts)
            if all_match:
                return True
        return False
    except Exception as e:
        print(f"[DEBUG] Error in matches_name: {e}")
        return False


def format_results(user_question, sql, results):
    """
    Format results in a readable way using Gemini.
    """
    if "error" in results:
        return f"Error: {results['error']}"
    
    if results['count'] == 0:
        return "No results found."
    
    # Show first 3 results
    sample_data = json.dumps(results['data'][:3], ensure_ascii=False, indent=2)
    
    prompt = f"""
User asked: {user_question}
SQL query: {sql}
Found {results['count']} results.

Sample data (first 3):
{sample_data}

Provide a helpful answer in Arabic summarizing the results. Include key details like case numbers, names, dates.
"""
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Found {results['count']} results but couldn't format: {e}"

def main():
    print("=" * 60)
    print("Legal Database Chat (Simple Version)")
    print("=" * 60)
    
    # Check if question provided as argument
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"\nQuestion: {question}")
        
        # Step 1: Generate SQL
        print("\nGenerating SQL...")
        sql = get_sql_from_gemini(question)
        if not sql:
            print("Failed to generate SQL")
            return
        
        print(f"SQL: {sql}")
        
        # Step 2: Execute SQL
        print("\nExecuting query...")
        results = execute_sql(sql, question)
        
        # Step 3: Format results
        print("\nFormatting results...")
        answer = format_results(question, sql, results)
        
        print("\n" + "=" * 60)
        print("ANSWER:")
        print("=" * 60)
        print(answer)
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
        sql = get_sql_from_gemini(question)
        if not sql:
            print("Failed to generate SQL\n")
            continue
        
        print(f"[SQL: {sql}]")
        
        print("[Executing...]")
        results = execute_sql(sql, question)
        
        print("[Formatting...]")
        answer = format_results(question, sql, results)
        
        print(f"\nAssistant: {answer}\n")
        print("-" * 60)

if __name__ == "__main__":
    main()
