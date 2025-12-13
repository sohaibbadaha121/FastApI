import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models import Document, Entity

db = SessionLocal()
doc = db.query(Document).filter(Document.filename == "test.pdf").first()
if doc:
    ent = db.query(Entity).filter(Entity.document_id == doc.id).first()
    if ent:
        print(f"test.pdf Case Number: {ent.case_number}")
        print(f"test.pdf Court: {ent.court_name}")
    else:
        print("test.pdf has no entities")
else:
    print("test.pdf not found")
db.close()
