import sqlite3
import json
import shutil
import os

DB_PATH = "legal_documents.db"
BACKUP_PATH = "legal_documents_backup.db"

def fix_unicode_encoding():
    print("=" * 60)
    print("FIXING DATABASE UNICODE ENCODING")
    print("=" * 60)

    # 1. Create a backup first!
    if os.path.exists(DB_PATH):
        print(f"Creating backup at {BACKUP_PATH}...")
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print("Backup created successfully.")
    else:
        print(f"Error: Database {DB_PATH} not found.")
        return

    # 2. Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 3. Get all entities
    cursor.execute("SELECT id, plaintiff, defendant, judge, plaintiff_lawyer, defendant_lawyer, legal_articles, raw_entities FROM entities")
    rows = cursor.fetchall()
    
    print(f"\nProcessing {len(rows)} rows...")
    
    updates_count = 0
    
    columns_to_fix = [
        'plaintiff', 'defendant', 'judge', 'plaintiff_lawyer', 'defendant_lawyer',
        'legal_articles', 'raw_entities'
    ]
    
    for row in rows:
        row_id = row['id']
        update_data = {}
        needs_update = False
        
        for col in columns_to_fix:
            val = row[col]
            if val:
                try:
                    # 1. Parse the JSON (decodes \u0627...)
                    parsed = json.loads(val)
                    
                    # 2. Dump it back WITHOUT ascii escaping (ensure_ascii=False)
                    # This saves "أحمد" as "أحمد", not "\u0623..."
                    fixed_val = json.dumps(parsed, ensure_ascii=False)
                    
                    # Check if it actually changed
                    if fixed_val != val:
                        update_data[col] = fixed_val
                        needs_update = True
                        
                except Exception as e:
                    print(f"Warning: Could not parse {col} for ID {row_id}: {e}")
        
        if needs_update:
            # Construct UPDATE query dynamically
            set_clause = ", ".join([f"{col} = ?" for col in update_data.keys()])
            values = list(update_data.values())
            values.append(row_id)
            
            sql = f"UPDATE entities SET {set_clause} WHERE id = ?"
            cursor.execute(sql, values)
            updates_count += 1

    conn.commit()
    conn.close()
    
    print(f"\nSuccess! Updated {updates_count} rows.")
    print("The database now contains readable Arabic text.")
    print("=" * 60)

if __name__ == "__main__":
    fix_unicode_encoding()
