import os
import sys
import time
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI")

print(f"API Key: {api_key[:20]}..." if api_key else "No API key")

genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    print("Sending test request to Gemini...")
    
    response = model.generate_content("Say 'Hello, I am working!' in one sentence.")
    
    print("SUCCESS!")
    print(f"Response: {response.text}")
    
except Exception as e:
    print(f"FAILED: {type(e).__name__}")
    print(f"Error: {str(e)}")
    
    
    with open("gemini_error.txt", "w", encoding="utf-8") as f:
        import traceback
        f.write(f"Error Type: {type(e).__name__}\n")
        f.write(f"Error Message: {str(e)}\n\n")
        f.write("Full Traceback:\n")
        f.write(traceback.format_exc())
    
    print("\nFull error written to gemini_error.txt")
