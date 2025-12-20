import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
import json
from app.pdf_processor import extract_text_from_pdf

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

pdf_path = "legal/PDFPre.pdf"
print(f"Testing with: {pdf_path}\n")

text = extract_text_from_pdf(pdf_path)
print(f"Extracted {len(text)} characters\n")

prompt = f"""
Extract entities from this Arabic legal text and return as JSON.

Extract:
- رقم_القضية (case number)
- اسم_المحكمة (court name)  
- المدعي (plaintiff)
- المدعى_عليه (defendant)

Return ONLY this JSON structure, nothing else:
{{
  "الكيانات": {{
    "رقم_القضية": "value or null",
    "اسم_المحكمة": "value or null",
    "المدعي": "value or null",
    "المدعى_عليه": "value or null"
  }},
  "العلاقات": []
}}

Text (first 2000 chars):
{text[:2000]}
"""

print("Sending to Gemini...\n")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    response_text = response.text
    
    print("="*60)
    print("RAW RESPONSE:")
    print("="*60)
    print(response_text)
    print("="*60)
    
    try:
        parsed = json.loads(response_text)
        print("\nJSON parsed successfully!")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\nJSON parse error: {e}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
