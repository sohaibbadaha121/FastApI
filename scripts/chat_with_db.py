import os
import sys
import json
import sqlite3
import unicodedata
import google.generativeai as genai
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    sys.exit(1)

genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"

DB_PATH = "legal_documents.db"

def normalize_arabic(text):
    """
    Normalize Arabic text for better matching.
    Removes diacritics and normalizes Unicode.
    """
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', str(text))
    arabic_diacritics = '\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0653\u0654\u0655\u0656\u0657\u0658'
    for mark in arabic_diacritics:
        text = text.replace(mark, '')
    return text.strip()

def search_in_json_field(json_text, search_terms):
    """
    Search for terms in a JSON field (stored as text).
    Handles both JSON arrays and strings.
    """
    if not json_text:
        return False
    
    # Normalize the JSON text
    json_text_normalized = normalize_arabic(json_text.lower())
    
    # Check each search term
    for term in search_terms:
        term_normalized = normalize_arabic(term.lower())
        if term_normalized not in json_text_normalized:
            return False
    
    return True

def get_schema_context():
    """
    Returns a string describing the database schema for the LLM.
    """
    return """
    You are an expert SQL assistant. You are querying an SQLite database named 'legal_documents.db'.
    
    Here is the schema:
    
    1. Table: documents
       - id (Integer, PK)
       - filename (String)
       - upload_date (DateTime)
       - status (String)
       - raw_text (Text)
       
    2. Table: entities (Contains extracted legal case info)
       - id (Integer, PK)
       - document_id (Integer, FK -> documents.id)
       - case_number (String)
       - court_name (String)
       - judgment_date (String)
       - case_type (String)
       
       JSON Columns (stored as TEXT):
       - plaintiff (JSON Array of names)
       - defendant (JSON Array of names)
       - plaintiff_lawyer (JSON Array)
       - defendant_lawyer (JSON Array)
       - judge (JSON Array or String)
       - financial_amounts (JSON)
       - compensations (JSON)
       
       Text Columns:
       - decision (Text - The final judgment summary)
       - verdict (Text - The specific ruling)
    
    3. Table: entity_relationships
       - from_entity (String)
       - relationship_type (String)
       - to_entity (String)
       
    RULES:
    1. Return ONLY the SQL query. No markdown formatting (no ```sql ... ```).
    2. USE ONLY 'SELECT' statements. Do not modify the database.
    3. **IMPORTANT**: When user asks about names in JSON columns (judge, plaintiff, defendant, lawyers),
       you should SELECT ALL rows from entities table and let Python code do the filtering.
       Example: User asks "find judge ايمن زهران" -> Return: SELECT * FROM entities
       (Don't use WHERE LIKE on JSON columns - Python will handle the search)
    4. For non-JSON columns (like court_name, case_type), you can use normal WHERE clauses.
    5. For counting or aggregations on non-JSON fields, use normal SQL.
    
    Examples:
    - "Find cases with judge ايمن زهران" -> SELECT * FROM entities
    - "Find cases in محكمة النقض" -> SELECT * FROM entities WHERE court_name LIKE '%محكمة النقض%'
    - "How many cases?" -> SELECT COUNT(*) FROM entities
    - "Find plaintiff أحمد" -> SELECT * FROM entities
    """

def get_sql_from_llm(user_query):
    """
    Asks Gemini to translate natural language to SQL.
    Returns: (sql_query, filter_info)
    filter_info: dict with filtering instructions for Python
    """
    model = genai.GenerativeModel(MODEL_NAME)
    
    schema_context = get_schema_context()
    
    prompt = f"""
    {schema_context}
    
    User Question: "{user_query}"
    
    If the question involves searching names in JSON columns (judge, plaintiff, defendant, lawyers),
    return SQL that selects all entities: SELECT * FROM entities
    
    Otherwise, generate appropriate SQL query.
    
    Return ONLY the SQL query:
    """
    
    try:
        response = model.generate_content(prompt)
        sql = response.text.strip()
        # Clean up markdown
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        
        # Detect if we need to filter in Python
        filter_info = extract_filter_info(user_query)
        
        return sql, filter_info
    except Exception as e:
        print(f"Error generating SQL: {e}")
        return None, None

def extract_filter_info(user_query):
    """
    Extract filtering information from user query.
    Returns dict with filter field and search terms.
    """
    query_lower = user_query.lower()
    
    # Detect filter type
    if 'قاضي' in user_query or 'judge' in query_lower:
        field = 'judge'
    elif 'مدعي' in user_query or 'plaintiff' in query_lower:
        field = 'plaintiff'
    elif 'مدعى عليه' in user_query or 'defendant' in query_lower:
        field = 'defendant'
    elif 'محامي' in user_query and ('مدعي' in user_query or 'plaintiff' in query_lower):
        field = 'plaintiff_lawyer'
    elif 'محامي' in user_query and ('مدعى عليه' in user_query or 'defendant' in query_lower):
        field = 'defendant_lawyer'
    elif 'محامي' in user_query or 'lawyer' in query_lower:
        field = 'lawyer'  # Search both
    else:
        return None
    
    # Extract search terms (simple approach - split by spaces)
    # Remove common question words
    stop_words = ['اعطيني', 'جميع', 'القضايا', 'الي', 'كان', 'فيها', 'هو', 'find', 'all', 'cases', 'with', 'where', 'the', 'is', 'was']
    words = user_query.split()
    search_terms = [w for w in words if w not in stop_words and len(w) > 1]
    
    return {'field': field, 'terms': search_terms}

def execute_query(sql, filter_info=None):
    """
    Executes the SQL query and applies Python-based filtering if needed.
    """
    if not sql.lower().startswith("select"):
        return "Error: Only SELECT queries are allowed for safety."
        
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # Convert rows to list of dicts
        results = [dict(row) for row in rows]
        
        conn.close()
        
        # Apply Python filtering if needed
        if filter_info and results:
            results = filter_results_in_python(results, filter_info)
        
        return results
    except Exception as e:
        return f"Database Error: {e}"

def filter_results_in_python(results, filter_info):
    """
    Filter results based on JSON field content using Python.
    """
    field = filter_info.get('field')
    terms = filter_info.get('terms', [])
    
    if not field or not terms:
        return results
    
    filtered = []
    
    for row in results:
        if field == 'lawyer':
            if search_in_json_field(row.get('plaintiff_lawyer'), terms) or \
               search_in_json_field(row.get('defendant_lawyer'), terms):
                filtered.append(row)
        else:
            if search_in_json_field(row.get(field), terms):
                filtered.append(row)
    
    return filtered

def explain_results(user_query, results, sql_used):
    """
    Asks Gemini to explain the results in natural language.
    """
    if isinstance(results, str) and results.startswith("Database Error"):
        return f"Could not answer due to technical error: {results}"
    
    if not results:
        return "No results found matching your query."

    # Limit results summary
    results_summary = json.dumps(results[:5], ensure_ascii=False)  
    count = len(results)
    
    model = genai.GenerativeModel(MODEL_NAME)
    
    prompt = f"""
    User Question: "{user_query}"
    SQL Used: "{sql_used}"
    
    Query Results (Top 5 of {count} total results):
    {results_summary}
    
    Please provide a helpful, natural language answer in Arabic summarizing these results.
    Include relevant details like case numbers, dates, and key information.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error explaining results: {e}"

def main():
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"Query: {user_input}")
        
        sql_query, filter_info = get_sql_from_llm(user_input)
        if not sql_query:
            print("Failed to generate SQL.")
            return
            
        print(f"SQL: {sql_query}")
        if filter_info:
            print(f"Python Filter: {filter_info}")
        
        results = execute_query(sql_query, filter_info)
        answer = explain_results(user_input, results, sql_query)
        print(f"Answer: {answer}")
        return

    print("Welcome to the Legal DB Chat Assistant!")
    print("Ask questions like: 'Find all cases where the plaintiff is Ahmad' or 'How many documents are there?'")
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError:
            break
            
        if user_input.lower() in ["exit", "quit"]:
            break
            
        if not user_input:
            continue
            
        print("\nThinking...")
        
        # 1. Get SQL and filter info
        sql_query, filter_info = get_sql_from_llm(user_input)
        if not sql_query:
            print("Sorry, I couldn't generate a query for that.")
            continue
            
        print(f"Generated SQL: {sql_query}")
        if filter_info:
            print(f"Applying Python filter: {filter_info}")
        
        # 2. Execute with filtering
        results = execute_query(sql_query, filter_info)
        
        # 3. Explain Results
        answer = explain_results(user_input, results, sql_query)
        
        print(f"\nAssistant: {answer}\n")
        print("-" * 50)

if __name__ == "__main__":
    main()