import sqlite3
import json

DB_PATH = "legal_documents.db"

print("=" * 60)
print("DIRECT DATABASE TEST")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


print("\n1. TABLES IN DATABASE:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"   - {table[0]}")


print("\n2. TOTAL DOCUMENTS:")
cursor.execute("SELECT COUNT(*) as count FROM documents")
doc_count = cursor.fetchone()
print(f"   Documents: {doc_count[0]}")

print("\n3. TOTAL ENTITIES:")
cursor.execute("SELECT COUNT(*) as count FROM entities")
entity_count = cursor.fetchone()
print(f"   Entities: {entity_count[0]}")


print("\n4. ALL DOCUMENTS:")
cursor.execute("SELECT id, filename, status FROM documents")
docs = cursor.fetchall()
for doc in docs:
    print(f"   ID: {doc['id']}, File: {doc['filename']}, Status: {doc['status']}")


print("\n5. SAMPLE ENTITY DATA:")
cursor.execute("SELECT id, document_id, case_number, court_name, judge FROM entities LIMIT 3")
entities = cursor.fetchall()
for entity in entities:
    print(f"\n   Entity ID: {entity['id']}")
    print(f"   Document ID: {entity['document_id']}")
    print(f"   Case Number: {entity['case_number']}")
    print(f"   Court Name: {entity['court_name']}")
    print(f"   Judge (raw): {entity['judge']}")
    
    if entity['judge']:
        try:
            judge_parsed = json.loads(entity['judge'])
            print(f"   Judge (parsed): {judge_parsed}")
        except:
            print(f"   Judge (not JSON): {entity['judge']}")

print("\n6. SEARCH TEST - Find 'ايمن' in judge field:")
cursor.execute("SELECT id, case_number, judge FROM entities WHERE judge LIKE '%ايمن%'")
results = cursor.fetchall()
print(f"   Found {len(results)} results")
for result in results:
    print(f"   - Case: {result['case_number']}, Judge: {result['judge']}")

print("\n7. SEARCH TEST - Find 'زهران' in judge field:")
cursor.execute("SELECT id, case_number, judge FROM entities WHERE judge LIKE '%زهران%'")
results = cursor.fetchall()
print(f"   Found {len(results)} results")
for result in results:
    print(f"   - Case: {result['case_number']}, Judge: {result['judge']}")

print("\n8. ALL JUDGES IN DATABASE:")
cursor.execute("SELECT DISTINCT judge FROM entities WHERE judge IS NOT NULL")
judges = cursor.fetchall()
for judge in judges:
    print(f"   Raw: {judge['judge']}")
    if judge['judge']:
        try:
            parsed = json.loads(judge['judge'])
            print(f"   Parsed: {parsed}")
        except:
            pass

conn.close()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
