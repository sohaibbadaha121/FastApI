import sqlite3
import json

conn = sqlite3.connect('legal_documents.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT case_number, judge FROM entities WHERE case_number = '3433/2013'")
row = cursor.fetchone()

print(f"Case: {row['case_number']}")
print(f"\nJudge field (raw):")
print(repr(row['judge']))

print(f"\nJudge field (display):")
print(row['judge'])

print(f"\nTrying to parse as JSON:")
try:
    judges = json.loads(row['judge'])
    print(f"Success! Parsed: {judges}")
    print(f"Type: {type(judges)}")
    
    if isinstance(judges, list):
        for judge in judges:
            print(f"\nJudge: {judge}")
            print(f"Contains 'ايمن': {'ايمن' in judge}")
            print(f"Contains 'زهران': {'زهران' in judge}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
