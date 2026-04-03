
import json
from app.database import SessionLocal
from app.models import Entity
from sqlalchemy import text

def test():
    session = SessionLocal()
    keyword = "تامر"
    
    print("--- Inspecting DB Content ---")
    entities = session.query(Entity).filter(Entity.case_number.like("%795%")).all()
    
    for ent in entities:
        print(f"ID: {ent.id}")
        print(f"Plaintiff (Python Object): {ent.plaintiff} (Type: {type(ent.plaintiff)})")
        
        sql = text("SELECT plaintiff FROM entities WHERE id = :id")
        raw_val = session.execute(sql, {"id": ent.id}).scalar()
        print(f"Plaintiff (Raw DB String): {raw_val!r}")
        
    session.close()

if __name__ == "__main__":
    test()
