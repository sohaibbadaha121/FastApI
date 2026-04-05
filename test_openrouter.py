import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER")

if not api_key:
    print("Error: No OpenRouter API key found.")
    exit(1)

print("Checking API key...")

try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    # Trying Google's Gemini 2.0 Flash (Completely Free & Lightning Fast)
    MODEL_NAME = os.getenv("OPENROUTER_MODEL")
    print(f"Connecting using model: {MODEL_NAME}")
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": "Just say yes."}]
    )
    
    answer = response.choices[0].message.content
    print(f"Success! Model reply: {answer}")
    
except Exception as e:
    print("Connection failed:")
    print(e)
