import os
import sqlite3
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values
import sys

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import engine
from app.models import Base

def migrate():
    print("Starting migration to Neon PostgreSQL...")
    
    POSTGRES_URL = os.getenv("DATABASE_URL")
    if not POSTGRES_URL or not POSTGRES_URL.startswith("postgres"):
        print("Error: Invalid or missing DATABASE_URL in .env")
        return

    try:
        print("Creating tables in PostgreSQL...")
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating tables: {e}")
        return
    
    SQLITE_DB = "legal_documents.db"
    if not os.path.exists(SQLITE_DB):
        print(f"Warning: {SQLITE_DB} not found. Tables created without migrating data.")
        return
        
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        pg_conn = psycopg2.connect(POSTGRES_URL)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"Connection to Neon failed: {e}")
        return

    tables = ["documents", "entities", "entity_relationships"] 
    
    for table in tables:
        try:
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
        except sqlite3.OperationalError:
            continue
            
        if not rows:
            print(f"Skipping empty table: {table}")
            continue
            
        print(f"Migrating table {table} ({len(rows)} records)...")
        column_names = [description[0] for description in sqlite_cursor.description]
        cols_str = ",".join(column_names)
        
        pg_cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
        
        insert_query = f"INSERT INTO {table} ({cols_str}) VALUES %s"
        execute_values(pg_cursor, insert_query, rows)
        
    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
