import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import extract_text_from_pdf

pdf_path = "legal/test.pdf"
text = extract_text_from_pdf(pdf_path)

print(f"PDF: {pdf_path}")
print(f"Total characters: {len(text)}")
print(f"Total words (approx): {len(text.split())}")
print(f"\n{'='*60}")
print("FIRST 500 CHARACTERS:")
print(f"{'='*60}")
print(text[:500])
print(f"\n{'='*60}")
print("LAST 500 CHARACTERS:")
print(f"{'='*60}")
print(text[-500:])
