"""Clear the database to reprocess"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Document

db = SessionLocal()

print("Deleting all documents from database...")
db.query(Document).delete()
db.commit()

print("Database cleared!")
print("Now run: python process_legal_pdfs.py")

db.close()
