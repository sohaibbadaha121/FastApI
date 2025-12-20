
import json
from app.database import SessionLocal
from app.models import Entity
from sqlalchemy import cast, String

def test():
    session = SessionLocal()
    keyword = "تامر"
    print(f"Testing search for keyword: {keyword}")

    print("1. Testing Plain Text Match...")
    res1 = session.query(Entity).filter(cast(Entity.plaintiff, String).ilike(f"%{keyword}%")).all()
    print(f"   found {len(res1)} results.")


    dumped = json.dumps(keyword, ensure_ascii=True).strip('"')
    print(f"2. Testing JSON Dump (Standard): {dumped}")
    res2 = session.query(Entity).filter(cast(Entity.plaintiff, String).ilike(f"%{dumped}%")).all()
    print(f"   found {len(res2)} results.")

    escaped = dumped.replace('\\', '\\\\')
    print(f"3. Testing JSON Dump (Escaped): {escaped}")
    res3 = session.query(Entity).filter(cast(Entity.plaintiff, String).ilike(f"%{escaped}%")).all()
    print(f"   found {len(res3)} results.")
    
    print("\n--- DB Inspection ---")
    ent = session.query(Entity).filter(Entity.case_number.like("%795%")).first()
    if ent:
        print(f"Case 795 Plaintiff Raw: {ent.plaintiff}")
        raw_rows = session.execute("SELECT plaintiff FROM entities WHERE case_number LIKE '%795%'").fetchall()
        for r in raw_rows:
            print(f"Raw SQL Value: {r[0]}")

    session.close()

if __name__ == "__main__":
    test()
