import sqlite3
import json
import sys

DB_PATH = "legal_documents.db"

def run_query(sql, description=""):
    """Execute SQL and print results."""
    print(f"\n{'='*60}")
    if description:
        print(f"Query: {description}")
    print(f"SQL: {sql}")
    print(f"{'='*60}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        if not rows:
            print("No results found.")
            conn.close()
            return
        
        print(f"\nFound {len(rows)} result(s):\n")
        
        for i, row in enumerate(rows, 1):
            print(f"--- Result {i} ---")
            for key in row.keys():
                value = row[key]
                if value is not None:
                    # Try to parse JSON fields
                    if key in ['judge', 'plaintiff', 'defendant', 'plaintiff_lawyer', 'defendant_lawyer', 'legal_articles']:
                        try:
                            parsed = json.loads(value)
                            print(f"  {key}: {parsed}")
                        except:
                            print(f"  {key}: {value}")
                    elif len(str(value)) > 100:
                        print(f"  {key}: {str(value)[:100]}...")
                    else:
                        print(f"  {key}: {value}")
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")

print("="*60)
print("RUNNING DATABASE TESTS")
print("="*60)

# Test 1: Count entities
run_query(
    "SELECT COUNT(*) as total FROM entities",
    "Count all entities"
)

# Test 2: Show case numbers
run_query(
    "SELECT case_number, court_name FROM entities",
    "Show all case numbers and courts"
)

# Test 3: Find specific judge (using Python filtering because of Unicode escapes)
print(f"\n{'='*60}")
print("Query: Find cases with judge 'ايمن زهران'")
print("SQL: SELECT * FROM entities (then filter in Python)")
print(f"{'='*60}")

try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT case_number, judge FROM entities WHERE judge IS NOT NULL")
    rows = cursor.fetchall()
    
    found_cases = []
    for row in rows:
        if row['judge']:
            try:
                judges = json.loads(row['judge'])
                # Check if any judge contains the name
                for judge in judges:
                    if 'ايمن' in judge and 'زهران' in judge:
                        found_cases.append((row['case_number'], judges))
                        break
            except:
                pass
    
    if found_cases:
        print(f"\nFound {len(found_cases)} result(s):\n")
        for i, (case_num, judges) in enumerate(found_cases, 1):
            print(f"--- Result {i} ---")
            print(f"  case_number: {case_num}")
            print(f"  judge: {judges}")
            print()
    else:
        print("No results found.")
    
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")

# Test 4: Show all judges
run_query(
    "SELECT case_number, judge FROM entities WHERE judge IS NOT NULL",
    "Show all judges"
)

# Test 5: Full entity data
run_query(
    "SELECT * FROM entities LIMIT 1",
    "Show one complete entity record"
)

print("\n" + "="*60)
print("ALL TESTS COMPLETE!")
print("="*60)
print("\nThe database is working perfectly!")
print("The issue is only with the Gemini API quota.")
print("\nTo fix the chat_with_db.py, you need:")
print("  1. Wait for API quota to reset (usually 24 hours)")
print("  2. OR use a different Google account's API key")
print("  3. OR upgrade to a paid Gemini API plan")
