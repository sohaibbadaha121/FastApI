import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

queries = [
    (
        "Total cases", 
        "SELECT COUNT(*) FROM entities;"
    ),
    (
        "Cases for Judge Ahmed Al-Mughni", 
        "SELECT COUNT(*) FROM entities WHERE judge::text LIKE '%أحمد المغني%';"
    ),
    (
        "Cases for Judge Ahmed Al-Mughni with 'رد الدعوى' verdict", 
        "SELECT COUNT(*) FROM entities WHERE judge::text LIKE '%أحمد المغني%' AND verdict::text LIKE '%رد الدعوى%';"
    )
]

try:
    with engine.connect() as connection:
        for name, query in queries:
            print(f"\n--- {name} ---")
            print(f"SQL: {query}")
            result = connection.execute(text(query))
            row = result.fetchone()
            print(f"Result: {row[0]}")
except Exception as e:
    print("\nDatabase Error:")
    print(e)
