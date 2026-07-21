"""DB query validation - understand actual data format."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from sqlalchemy import text

with engine.connect() as con:
    print("=== judgment_date format samples ===")
    for row in con.execute(text("SELECT case_number, judgment_date FROM entities ORDER BY case_number LIMIT 8")).mappings():
        print(" ", dict(row))

    print()
    print("=== Dates containing /9/2021 ===")
    for row in con.execute(text("SELECT case_number, judgment_date FROM entities WHERE judgment_date LIKE '%/9/2021'")).mappings():
        print(" ", dict(row))

    print()
    print("=== plaintiff JSON LIKE search for حسام ===")
    for row in con.execute(text("SELECT case_number, plaintiff FROM entities WHERE plaintiff::text LIKE '%حسام%'")).mappings():
        print(" ", dict(row))

    print()
    print("=== COUNT case_type = مدني ===")
    val = con.execute(text("SELECT COUNT(*) FROM entities WHERE case_type = 'مدني'")).scalar()
    print(" ", val)

    print()
    print("=== judge + chief_judge sample ===")
    for row in con.execute(text("SELECT case_number, judge, chief_judge FROM entities LIMIT 3")).mappings():
        print(" ", dict(row))

    print()
    print("=== legal_articles sample ===")
    for row in con.execute(text("SELECT case_number, legal_articles FROM entities WHERE legal_articles IS NOT NULL LIMIT 3")).mappings():
        print(" ", dict(row))

    print()
    print("=== defendant_lawyer for شركة ترست ===")
    for row in con.execute(text("SELECT case_number, defendant FROM entities WHERE defendant::text LIKE '%ترست%'")).mappings():
        print(" ", dict(row))
