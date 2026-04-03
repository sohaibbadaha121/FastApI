import sqlite3
import json

DB_PATH = "legal_documents.db"

def manual_verify():
    print("=" * 60)
    print("MANUAL VERIFICATION (NO AI)")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tests = [
        {
            "name": "1. Find case numbers for Judge 'Ayman Zahran'",
            "sql": "SELECT case_number FROM entities WHERE judge LIKE '%ايمن زهران%'",
            "expect_count": True
        },
        {
            "name": "2. Count cases for Judge 'Ahmad Al-Mughni'",
            "sql": "SELECT COUNT(*) as total FROM entities WHERE judge LIKE '%أحمد المغني%'",
            "expect_count": False 
        },
        {
            "name": "3. Find cases in 'Supreme Court' (المحكمة العليا)",
            "sql": "SELECT case_number, court_name FROM entities WHERE court_name LIKE '%المحكمة العليا%'",
            "expect_count": True
        },
        {
            "name": "4. General Count of all cases",
            "sql": "SELECT COUNT(*) as total FROM entities",
            "expect_count": False
        }
    ]
    
    for test in tests:
        print(f"\n--- TEST: {test['name']} ---")
        print(f"SQL: {test['sql']}")
        cursor.execute(test['sql'])
        rows = cursor.fetchall()
        
        if test['expect_count']:
            print(f"Found {len(rows)} row(s):")
            for row in rows:
                # Print first few columns dynamically
                vals = [str(row[key]) for key in row.keys()]
                print(f" - {', '.join(vals)}")
        else:
            # For COUNT queries, print the value directly
            # SQLite returns row with key 'total' or similar
            val = rows[0][0]
            print(f"Result: {val}")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("If these results look correct, the backend logic is 100% fixed.")
    print("=" * 60)

if __name__ == "__main__":
    manual_verify()
