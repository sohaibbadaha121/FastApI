"""Simple test - process one PDF"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
from app.pdf_processor import extract_text_from_pdf

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Extract text from first PDF
pdf_path = "legal/PDFPre.pdf"
print(f"Reading: {pdf_path}")
text = extract_text_from_pdf(pdf_path)
print(f"Extracted: {len(text)} characters")
print(f"First 200 chars: {text[:200]}")

# Test Gemini
print("\nTesting Gemini...")
try:
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    
    # Simple prompt
    prompt = f"""
Extract the case number (رقم القضية) from this Arabic legal text.
Return only JSON with one field: {{"رقم_القضية": "value"}}

Text:
{text[:1000]}
"""
    
    print("Sending to Gemini...")
    response = model.generate_content(prompt)
    print(f" Response: {response.text}")
    
except Exception as e:
    print(f" Error: {e}")
    import traceback
    traceback.print_exc()
