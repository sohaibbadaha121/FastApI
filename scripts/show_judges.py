import sqlite3
import json

DB_PATH = "legal_documents.db"

# Connect to database
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Test: Get all judges
print("ALL JUDGES IN DATABASE:")
cursor.execute("SELECT id, case_number, judge FROM entities WHERE judge IS NOT NULL")
entities = cursor.fetchall()

for entity in entities:
    print(f"\nCase Number: {entity['case_number']}")
    print(f"Judge (raw): {repr(entity['judge'])}")
    
    if entity['judge']:
        try:
            parsed = json.loads(entity['judge'])
            print(f"Judge (parsed): {parsed}")
        except Exception as e:
            print(f"Could not parse: {e}")

conn.close()
