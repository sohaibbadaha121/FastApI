"""Quick verification that all packages are installed"""
import sys

print("=" * 60)
print("📦 Checking Installed Packages")
print("=" * 60)

packages = [
    ("sqlalchemy", "SQLAlchemy"),
    ("PyPDF2", "PyPDF2"),
    ("google.generativeai", "Google Generative AI"),
    ("fastapi", "FastAPI"),
    ("pydantic", "Pydantic"),
    ("dotenv", "Python-dotenv"),
]

all_good = True

for package, name in packages:
    try:
        module = __import__(package)
        version = getattr(module, "__version__", "unknown")
        print(f"✅ {name}: {version}")
    except ImportError:
        print(f"❌ {name}: NOT INSTALLED")
        all_good = False

print("=" * 60)

if all_good:
    print("✅ All packages installed successfully!")
    print("\n🚀 You're ready to process PDFs!")
    print("\nNext steps:")
    print("  1. Add PDF files to 'legal' folder")
    print("  2. Run: python process_legal_pdfs.py")
else:
    print("❌ Some packages are missing!")
    print("\nRun: python -m pip install -r requirements.txt")

print("=" * 60)
