import sys
sys.path.insert(0, 'c:\\Users\\laith\\OneDrive\\Desktop\\FastApi\\scripts')

from chat_simple import filter_results_by_names, matches_name
import sqlite3
import json

conn = sqlite3.connect('legal_documents.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM entities")
rows = cursor.fetchall()
results = [dict(row) for row in rows]
conn.close()

print(f"Total entities: {len(results)}\n")

question = "اعطيني القضايا التي فيها القاضي ايمن زهران"
print(f"Question: {question}\n")

filtered = filter_results_by_names(results, question)
print(f"\nFiltered results: {len(filtered)}")

if filtered:
    for row in filtered:
        print(f"  Case: {row['case_number']}")
        print(f"  Judge: {row['judge']}")
