import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
import json

SQLITE_DB = "legal_documents.db"
POSTGRES_URL = "postgresql://pal_legal_db_user:AtXyP59q1meOu0aPRR63uR9tpUxOWVBR@dpg-d5mjvfur433s7388623g-a.virginia-postgres.render.com/pal_legal_db"

def migrate():
    print(" بدء عملية نقل البيانات...")
    
    if not os.path.exists(SQLITE_DB):
        print(f"خطأ: ملف {SQLITE_DB} غير موجود!")
        return

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()


    try:
        pg_conn = psycopg2.connect(POSTGRES_URL)
        pg_cursor = pg_conn.cursor()
        print(" تم الاتصال بقاعدة بيانات Render بنجاح.")
    except Exception as e:
        print(f" فشل الاتصال بـ Render: {e}")
        return

    tables = ["documents", "entities", "entity_relationships"]

    for table in tables:
        print(f" نقل جدول: {table}...")
        
        sqlite_cursor.execute(f"SELECT * FROM {table}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f" الجدول {table} فارغ، تخطي...")
            continue

        column_names = [description[0] for description in sqlite_cursor.description]
        cols_str = ",".join(column_names)
        placeholders = ",".join(["%s"] * len(column_names))

        cleaned_rows = []
        for row in rows:
            new_row = []
            for item in row:
                if isinstance(item, str) and (item.startswith('[') or item.startswith('{')):
                    try:
                        new_row.append(item) 
                    except:
                        new_row.append(item)
                else:
                    new_row.append(item)
            cleaned_rows.append(tuple(new_row))

        pg_cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")

        insert_query = f"INSERT INTO {table} ({cols_str}) VALUES %s"
        execute_values(pg_cursor, insert_query, cleaned_rows)
        
        print(f" تم نقل {len(rows)} سجل إلى {table}.")
        

    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()
    print("\n تمت عملية النقل بنجاح! جميع بياناتك الآن على Render.")

if __name__ == "__main__":
    migrate()
