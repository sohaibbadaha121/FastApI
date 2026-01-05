import sqlite3
import json

DB_PATH = "legal_documents.db"

def inspect_database_thoroughly():
    print("=" * 60)
    print("THOROUGH DATABASE INSPECTION")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"Tables found: {[t['name'] for t in tables]}")
    
    # 2. Inspect each table
    for table_row in tables:
        table_name = table_row['name']
        print(f"\n--- Intepecting Table: {table_name} ---")
        
        # Get Sample Row
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        sample = cursor.fetchone()
        
        if not sample:
            print("  (Empty table)")
            continue
            
        # Check all columns for likely encoded JSON or text
        for key in sample.keys():
            val = str(sample[key])
            
            # Look for the signature of escaped unicode: "\u06..."
            if "\\u06" in val:
                print(f"  [WARNING] Column '{key}' seems to have UNICODE ESCAPES!")
                print(f"     Preview: {val[:50]}...")
            else:
                pass 
                # print(f"  [OK] Column '{key}' looks clean.")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    inspect_database_thoroughly()
