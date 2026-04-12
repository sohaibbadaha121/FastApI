import os
from dotenv import load_dotenv
import google.generativeai as genai

def test_gemini():
    load_dotenv()
    
    api_key = os.getenv("GEMINI")
    if not api_key:
        print("API Key not found in .env file. Please check your GEMINI variable.")
        return
        
    print("API Key loaded successfully.")
    
    try:
        genai.configure(api_key=api_key)
        
        # Using the standard modern flash model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        print("Sending a test prompt to Gemini...")
        
        prompt = "مرحبا، هل تدعم اللغة العربية؟ أجب بكلمة واحدة فقط: نعم"
        response = model.generate_content(prompt)
        
        print("-" * 30)
        print("Gemini Response:")
        print(response.text)
        print("-" * 30)
        print("Test completed successfully. Gemini is working!")
        
    except Exception as e:
        print("\nAn error occurred while connecting to Gemini:")
        print(str(e))

if __name__ == "__main__":
    test_gemini()
