import sqlite3

conn = sqlite3.connect('legal_documents.db')
cursor = conn.cursor()

cursor.execute('SELECT judge FROM entities WHERE case_number = "3433/2013"')
result = cursor.fetchone()

print("Raw judge field:")
print(repr(result[0]))
print("\nActual content:")
print(result[0])

conn.close()
