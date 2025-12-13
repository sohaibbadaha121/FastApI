import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Testing Gemini API...")

try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("Say hello in Arabic")
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
