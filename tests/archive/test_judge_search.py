import sqlite3
import json

DB_PATH = "legal_documents.db"

print("="*60)
print("Testing: Find judge 'ايمن زهران'")
print("="*60)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT case_number, judge FROM entities WHERE judge IS NOT NULL")
rows = cursor.fetchall()

print(f"\nChecking {len(rows)} entities...")

found_cases = []
for row in rows:
    if row['judge']:
        try:
            judges = json.loads(row['judge'])
            print(f"\nCase {row['case_number']}: {judges}")
            
            # Check if any judge contains the name
            for judge in judges:
                if 'ايمن' in judge and 'زهران' in judge:
                    print(f"  ✓ MATCH FOUND!")
                    found_cases.append((row['case_number'], judges))
                    break
        except Exception as e:
            print(f"  Error parsing: {e}")

print("\n" + "="*60)
print("RESULTS:")
print("="*60)

if found_cases:
    print(f"\nFound {len(found_cases)} case(s) with judge 'ايمن زهران':\n")
    for case_num, judges in found_cases:
        print(f"  Case: {case_num}")
        print(f"  Judges: {judges}")
else:
    print("\nNo cases found with judge 'ايمن زهران'")

conn.close()
