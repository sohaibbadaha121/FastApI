import sqlite3
import json

DB_PATH = "legal_documents.db"

def execute_sql(sql):
    """Execute SQL query on the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        return results
    except Exception as e:
        return {"error": str(e)}

def format_results(results):
    """Format results in a readable way."""
    if isinstance(results, dict) and "error" in results:
        return f"Error: {results['error']}"
    
    if not results:
        return "No results found."
    
    output = f"Found {len(results)} result(s):\n\n"
    
    for i, row in enumerate(results, 1):
        output += f"Result {i}:\n"
        for key, value in row.items():
            if value is not None:
                # Try to parse JSON fields
                if key in ['judge', 'plaintiff', 'defendant', 'plaintiff_lawyer', 'defendant_lawyer']:
                    try:
                        parsed = json.loads(value)
                        output += f"  {key}: {parsed}\n"
                    except:
                        output += f"  {key}: {value}\n"
                else:
                    output += f"  {key}: {value}\n"
        output += "\n"
    
    return output

print("=" * 60)
print("DATABASE QUERY TESTER (No Gemini Required)")
print("=" * 60)

# Predefined queries you can test
queries = {
    "1": ("Count all entities", "SELECT COUNT(*) as total FROM entities"),
    "2": ("Show all case numbers", "SELECT case_number, court_name FROM entities"),
    "3": ("Find judge 'ايمن زهران'", "SELECT * FROM entities WHERE judge LIKE '%ايمن%' AND judge LIKE '%زهران%'"),
    "4": ("Show all judges", "SELECT case_number, judge FROM entities WHERE judge IS NOT NULL"),
    "5": ("Count documents", "SELECT COUNT(*) as total FROM documents"),
    "6": ("Show all data", "SELECT * FROM entities"),
}

print("\nAvailable Queries:")
for key, (desc, sql) in queries.items():
    print(f"  {key}. {desc}")
print("  c. Custom SQL query")
print("  q. Quit")

while True:
    print("\n" + "-" * 60)
    choice = input("Select query (1-6, c, or q): ").strip()
    
    if choice.lower() == 'q':
        print("Goodbye!")
        break
    
    if choice.lower() == 'c':
        sql = input("Enter SQL query: ").strip()
        if not sql.lower().startswith("select"):
            print("Only SELECT queries allowed!")
            continue
    elif choice in queries:
        desc, sql = queries[choice]
        print(f"\nQuery: {desc}")
    else:
        print("Invalid choice!")
        continue
    
    print(f"SQL: {sql}\n")
    print("Executing...")
    
    results = execute_sql(sql)
    output = format_results(results)
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(output)
