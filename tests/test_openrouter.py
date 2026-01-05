import os
import sys
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

# 1. Load Environment
env_file = find_dotenv()
if env_file:
    print(f"Loading environment from: {env_file}")
    load_dotenv(env_file, override=True)
else:
    print("Warning: No .env file found.")

# 2. Get API Key
# Try different common variable names including the one found in debug (OPEN_ROUTER)
api_key = (
    os.getenv("OPENROUTER_API_KEY") or 
    os.getenv("OPENROUTER_KEY") or 
    os.getenv("OPENROUTER") or
    os.getenv("OPEN_ROUTER") or
    os.getenv("OPEN_ROUTER_API_KEY")
)

if not api_key:
    # Try fallbacks or manual search
    for key, value in os.environ.items():
        if "OPENROUTER" in key.upper() and "KEY" in key.upper():
            api_key = value
            break

if api_key:
    mask_len = min(len(api_key) - 4, 8)
    masked = api_key[:mask_len] + "..." if len(api_key) > 4 else "Found"
    print(f"API Key found: Yes ({masked})")
else:
    print("ERROR: OpenRouter API key not found.")
    print("Please ensure 'OPENROUTER_API_KEY' is set in your .env file")
    sys.exit(1)

try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    model_name = "google/gemini-2.0-flash-exp:free"
    print(f"Sending test request to OpenRouter (using {model_name})...")
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "Say 'Hello, OpenRouter is working!' in one sentence."}
        ]
    )
    
    print("SUCCESS!")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"FAILED: {type(e).__name__}")
    print(f"Error: {str(e)}")
    
    with open("openrouter_error.txt", "w", encoding="utf-8") as f:
        import traceback
        f.write(f"Error Type: {type(e).__name__}\n")
        f.write(f"Error Message: {str(e)}\n\n")
        f.write("Full Traceback:\n")
        f.write(traceback.format_exc())
    
    print("\nFull error details written to openrouter_error.txt")
