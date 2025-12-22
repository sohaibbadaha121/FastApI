import sys
sys.path.insert(0, 'c:\\Users\\laith\\OneDrive\\Desktop\\FastApi\\scripts')

from chat_simple import filter_results_by_names
import sqlite3

# Get sample data
conn = sqlite3.connect('legal_documents.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM entities WHERE case_number = '3433/2013'")
row = cursor.fetchone()
result = dict(row)
conn.close()

print("Single entity:")
print(f"  Case: {result['case_number']}")
print(f"  Judge: {result['judge']}\n")

# Test with list containing just this one
results = [result]

question = "اعطيني القضايا التي فيها القاضي ايمن زهران"
print(f"Question: {question}\n")

# Manually check what the function will extract
keywords = {
    'قاضي': 'judge',
    'judge': 'judge',
}

field_to_search = None
for keyword, field in keywords.items():
    if keyword in question.lower():
        field_to_search = field
        print(f"Found keyword '{keyword}' -> field '{field}'")
        break

stop_words = ['اعطيني', 'جميع', 'القضايا', 'الي', 'كان', 'فيها', 'هو', 'التي', 'find', 'all', 'cases', 'with', 'where', 'the', 'is', 'was']
words = question.split()
name_parts = [w for w in words if w not in stop_words and w not in keywords.keys() and len(w) > 1]

print(f"Name parts extracted: {name_parts}\n")

# Now run the filter
filtered = filter_results_by_names(results, question)
print(f"\nFiltered results: {len(filtered)}")
