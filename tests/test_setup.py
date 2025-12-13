"""
Simple test to verify the database setup works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import Document, Entity, EntityRelationship

print("=" * 60)
print("🧪 Testing Database Setup")
print("=" * 60)

print("\n1️⃣ Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("   ✅ Tables created successfully!")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)


print("\n2️⃣ Checking database file...")
if os.path.exists("legal_documents.db"):
    print("   ✅ Database file exists: legal_documents.db")
else:
    print("   ❌ Database file not found!")
    exit(1)

print("\n3️⃣ Testing database connection...")
try:
    db = SessionLocal()
   
    count = db.query(Document).count()
    print(f"   ✅ Connection successful! Documents in database: {count}")
    db.close()
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print("\n4️⃣ Checking Gemini API key...")
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    print(f"   ✅ API key found: {api_key[:10]}...")
else:
    print("   ❌ API key not found in .env file!")
    exit(1)


print("\n5️⃣ Checking legal folder...")
if os.path.exists("legal"):
    pdf_files = [f for f in os.listdir("legal") if f.endswith('.pdf')]
    print(f"   ✅ Legal folder exists")
    print(f"   📁 PDF files found: {len(pdf_files)}")
    if pdf_files:
        for i, pdf in enumerate(pdf_files, 1):
            print(f"      {i}. {pdf}")
    else:
        print("   ⚠️  No PDF files yet - add some PDFs to test!")
else:
    print("   ❌ Legal folder not found!")

print("\n" + "=" * 60)
print("✅ All tests passed! You're ready to process PDFs!")
print("=" * 60)
print("\n💡 Next steps:")
print("   1. Add PDF files to the 'legal' folder")
print("   2. Run: python process_legal_pdfs.py")
print("=" * 60)
