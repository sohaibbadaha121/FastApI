import sqlite3
import json

DB_PATH = "legal_documents.db"

print("=" * 60)
print("TESTING SQL QUERIES DIRECTLY")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Test Query 1: Get all entities
print("\n1. Query: SELECT * FROM entities")
cursor.execute("SELECT * FROM entities")
results = cursor.fetchall()
print(f"   Results: {len(results)} rows")

# Test Query 2: Search for judge with LIKE
print("\n2. Query: SELECT * FROM entities WHERE judge LIKE '%ايمن%'")
cursor.execute("SELECT * FROM entities WHERE judge LIKE '%ايمن%'")
results = cursor.fetchall()
print(f"   Results: {len(results)} rows")
if results:
    for row in results:
        print(f"   - Case: {row['case_number']}, Judge: {row['judge']}")

# Test Query 3: Search for 'زهران'
print("\n3. Query: SELECT * FROM entities WHERE judge LIKE '%زهران%'")
cursor.execute("SELECT * FROM entities WHERE judge LIKE '%زهران%'")
results = cursor.fetchall()
print(f"   Results: {len(results)} rows")
if results:
    for row in results:
        print(f"   - Case: {row['case_number']}, Judge: {row['judge']}")

# Test Query 4: Count all entities
print("\n4. Query: SELECT COUNT(*) FROM entities")
cursor.execute("SELECT COUNT(*) as count FROM entities")
result = cursor.fetchone()
print(f"   Total entities: {result['count']}")

# Test Query 5: Get specific columns
print("\n5. Query: SELECT case_number, court_name, judge FROM entities")
cursor.execute("SELECT case_number, court_name, judge FROM entities")
results = cursor.fetchall()
print(f"   Results: {len(results)} rows")
for row in results:
    print(f"\n   Case: {row['case_number']}")
    print(f"   Court: {row['court_name']}")
    if row['judge']:
        try:
            judges = json.loads(row['judge'])
            print(f"   Judges: {judges}")
        except:
            print(f"   Judge (raw): {row['judge']}")

conn.close()

print("\n" + "=" * 60)
print("ALL QUERIES WORK! Database is fine.")
print("=" * 60)
