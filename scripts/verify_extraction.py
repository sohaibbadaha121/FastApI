
import sys
import os
# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.pdf_processor import extract_text_from_pdf

def test_extraction():
    pdf_path = r"c:\Users\laith\OneDrive\Desktop\FastApi\legal\newtest.pdf"
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    print(f"Testing extraction from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    
    if text:
        print("\n--- EXTRACTED TEXT (First 1000 chars) ---\n")
        print(text[:1000])
        print("\n--- END ---")
    else:
        print("Extraction failed or returned no text.")

if __name__ == "__main__":
    test_extraction()
