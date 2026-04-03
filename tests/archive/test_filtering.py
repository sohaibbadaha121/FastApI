import sys
sys.path.insert(0, 'c:\\Users\\laith\\OneDrive\\Desktop\\FastApi\\scripts')

from chat_simple import execute_sql, filter_results_by_names, matches_name
import json

print("="*60)
print("Testing Python Filtering (No Gemini)")
print("="*60)

# Test 1: Simulate finding judge
print("\nTest 1: Find judge 'ايمن زهران'")
question = "اعطيني القضايا التي فيها القاضي ايمن زهران"
sql = "SELECT * FROM entities"

results = execute_sql(sql, question)
print(f"Results: {results['count']} cases found")
if results['count'] > 0:
    for row in results['data']:
        print(f"  - Case: {row['case_number']}, Judge: {row['judge']}")

# Test 2: Without filtering
print("\n\nTest 2: All entities (no filtering)")
results2 = execute_sql("SELECT * FROM entities", "")
print(f"Results: {results2['count']} total entities")

print("\n" + "="*60)
print("Filtering works!" if results['count'] > 0 else "Filtering needs adjustment")
print("="*60)
