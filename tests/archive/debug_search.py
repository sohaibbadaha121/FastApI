import sqlite3

conn = sqlite3.connect('legal_documents.db')
cursor = conn.cursor()

print("Test 1: Search with space")
cursor.execute("SELECT case_number FROM entities WHERE judge LIKE '%ايمن زهران%'")
results = cursor.fetchall()
print(f"Results: {results}")

print("\nTest 2: Search with unicode in judge field")
cursor.execute("SELECT case_number, judge FROM entities WHERE case_number = '3433/2013'")
result = cursor.fetchone()
print(f"Case: {result[0]}")
print(f"Judge field contains 'ايمن زهران': {'ايمن زهران' in result[1]}")
print(f"Judge field: {result[1][:100]}")

print("\nTest 3: Try searching just 'زهران'")
cursor.execute("SELECT case_number FROM entities WHERE judge LIKE '%زهران%'")
results = cursor.fetchall()
print(f"Results: {results}")

conn.close()
